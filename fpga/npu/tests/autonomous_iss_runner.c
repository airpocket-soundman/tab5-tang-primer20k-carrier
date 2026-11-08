/* FPGA-local firmware ISA test, not an FPGA or performance qualification.
 * The pinned RV32 interpreter executes all control/FP math. Only the integer
 * accelerator MMIO endpoint is a host INT64 reference implementation. */
#include <rv32emu.h>
#include "riscv.h"
#include "../firmware/autonomous/abi.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Test-only accessor installed into the pinned upstream api.c by build script. */
extern void rv32emu_autonomous_install(rv32emu_t *,const riscv_io_t *,riscv_io_t *);
static rv32emu_t *vm;
static riscv_io_t original;
static uint32_t desc[13], status=AUTONOMOUS_READY|AUTONOMOUS_MEMORY_READY,error_code,firmware_finished,node_reg,stage_reg,app_error;
static uint64_t tiles,matrices,macs,read_ops,write_ops;
static int fault;
static int32_t partial[8*16*16];
static unsigned partial_count;
static uint32_t partial_key[10];
static const uint32_t capacity=128u*1024*1024;

static void fail(const char *s){if(!fault)fprintf(stderr,"ISS error: %s\n",s);fault=1;if(vm)rv32emu_halt(vm);}
static int range(uint64_t a,uint64_t n){return a<=capacity&&n<=capacity-a;}
static int qi(uint64_t a){if(!range(a,1)){fail("integer oracle source range");return 0;}return (int8_t)memory_read_b((uint32_t)a);}
static void put32(uint64_t a,int32_t v){if(!range(a,4)){fail("integer oracle target range");return;}memory_write_w((uint32_t)a,(const uint8_t*)&v);}
static int checked_sum(int64_t s,int32_t *v){if(s<INT32_MIN||s>INT32_MAX)return 0;*v=(int32_t)s;return 1;}
static int tile(void){
 const uint8_t *d=(const uint8_t*)desc;
 const unsigned ic=d[0],oc=d[1],oh=d[2],ow=d[3],k=d[4],stride=d[5],flags=d[6];
 const unsigned ih=(unsigned)d[8]|(unsigned)d[9]<<8,iw=(unsigned)d[10]|(unsigned)d[11]<<8;
 const int32_t oy=(int32_t)desc[3],ox=(int32_t)desc[4];
 const uint32_t a=desc[5],arp=desc[6],acp=desc[7],b=desc[8],bcp=desc[9],c=desc[10],crp=desc[11],ccp=desc[12];
 if(!ic||ic>16||!oc||oc>8||!oh||oh>16||!ow||ow>16||(k!=1&&k!=3)||(stride!=1&&stride!=2)||!ih||!iw||d[7]||(flags&~7u)||!(flags&4u)||a%16||b%16||c%16||arp%16||acp%16||bcp%16||crp%16||ccp%16||arp<iw||acp<(uint64_t)arp*ih||bcp<ic*k*k||crp<ow*4||ccp<(uint64_t)crp*oh||!range(a,(uint64_t)(ic-1)*acp+(uint64_t)(ih-1)*arp+iw)||!range(b,(uint64_t)(oc-1)*bcp+ic*k*k)||!range(c,(uint64_t)(oc-1)*ccp+(uint64_t)(oh-1)*crp+ow*4))return 0;
 const unsigned count=oc*oh*ow;
 const uint32_t key[]={oc,oh,ow,k,stride,desc[2],desc[3],desc[4],c,ccp};
 if(flags&1){memset(partial,0,sizeof partial);partial_count=count;memcpy(partial_key,key,sizeof key);}
 else if(partial_count!=count||memcmp(partial_key,key,sizeof key))return 0;
 for(unsigned z=0;z<oc;z++)for(unsigned y=0;y<oh;y++)for(unsigned x=0;x<ow;x++){
  int64_t sum=partial[(z*oh+y)*ow+x];
  for(unsigned i=0;i<ic;i++)for(unsigned ky=0;ky<k;ky++)for(unsigned kx=0;kx<k;kx++){
   const int64_t yy=(int64_t)oy+y*stride+ky,xx=(int64_t)ox+x*stride+kx;
   if(yy>=0&&xx>=0&&yy<ih&&xx<iw)sum+=qi((uint64_t)a+i*acp+(uint64_t)yy*arp+xx)*qi((uint64_t)b+z*bcp+(i*k+ky)*k+kx);
   ++macs;
  }
  int32_t v;if(!checked_sum(sum,&v))return 0;partial[(z*oh+y)*ow+x]=v;
  if(flags&2)put32((uint64_t)c+z*ccp+y*crp+x*4,v);
 }
 if(flags&2)partial_count=0;
 ++tiles;return !fault;
}
static int matrix(void){
 const uint32_t m=desc[0],k=desc[1],n=desc[2],a=desc[3],ap=desc[4],b=desc[5],bp=desc[6],c=desc[7],cp=desc[8];
 const uint64_t mp=((uint64_t)m+15)&~UINT64_C(15),kp=((uint64_t)k+15)&~UINT64_C(15);
 if(partial_count||!m||m>65535||!k||k>65535||!n||n>65535||a%16||b%16||c%16||ap%16||bp%16||cp%16||ap<mp||bp<kp||cp<mp*4||!range(a,(uint64_t)k*ap)||!range(b,(uint64_t)n*bp)||!range(c,(uint64_t)n*cp))return 0;
 for(unsigned col=0;col<n;col++)for(unsigned row=0;row<mp;row++){
  int64_t sum=0;for(unsigned q=0;q<k;q++)sum+=qi((uint64_t)a+q*ap+row)*qi((uint64_t)b+col*bp+q);
  int32_t v;if(!checked_sum(sum,&v))return 0;put32((uint64_t)c+col*cp+row*4,v);macs+=k;
 }
 ++matrices;return !fault;
}
static uint32_t mmio_read(uint32_t off){if(off==AUTONOMOUS_MMIO_STATUS)return status;if(off==AUTONOMOUS_MMIO_ERROR)return error_code;if(off==AUTONOMOUS_MMIO_EPOCH)return 1;if(off==AUTONOMOUS_MMIO_NODE)return node_reg;if(off==AUTONOMOUS_MMIO_STAGE)return stage_reg;if(off==AUTONOMOUS_MMIO_APP_ERROR)return app_error;fail("unsupported MMIO read");return 0;}
static void mmio_write(uint32_t off,uint32_t v){
 if(off==AUTONOMOUS_MMIO_NODE){node_reg=v;return;}
 if(off==AUTONOMOUS_MMIO_STAGE){stage_reg=v;return;}
 if(off==AUTONOMOUS_MMIO_APP_ERROR){app_error=v;return;}
 if(off==AUTONOMOUS_MMIO_FINISH&&(v==1||v==2)){firmware_finished=v;rv32emu_halt(vm);return;}
 if(off>=0x40&&off<=0x70&&!(off&3)){if(!(status&AUTONOMOUS_READY)){fail("descriptor write while endpoint not ready");return;}desc[(off-0x40)/4]=v;return;}
 if(off==AUTONOMOUS_MMIO_ACK&&v==1){if(status&AUTONOMOUS_BUSY){fail("ACK while busy");return;}if(status&AUTONOMOUS_ERROR)return;status=AUTONOMOUS_READY|AUTONOMOUS_MEMORY_READY;return;}
 if(off==AUTONOMOUS_MMIO_ABORT&&v==1){partial_count=0;status=AUTONOMOUS_ERROR|AUTONOMOUS_MEMORY_READY;error_code=8;return;}
 if(off==AUTONOMOUS_MMIO_COMMAND&&(v==1||v==2)){
  if(!(status&AUTONOMOUS_READY)){fail("command while not ready");return;}
  status=AUTONOMOUS_BUSY|AUTONOMOUS_MEMORY_READY;const int ok=v==1?tile():matrix();
  if(!ok){error_code=1;status=AUTONOMOUS_ERROR|AUTONOMOUS_DONE|AUTONOMOUS_MEMORY_READY;}
  else status=AUTONOMOUS_DONE|AUTONOMOUS_MEMORY_READY|((v==2||(((uint8_t*)desc)[6]&2))?AUTONOMOUS_RESULT_VALID:0);
  return;
 }
 fail("unsupported MMIO write");
}
static int is_mmio(uint32_t a){return a>=AUTONOMOUS_MMIO_BASE&&a<AUTONOMOUS_MMIO_BASE+0x100;}
static uint32_t read_word(riscv_t*r,uint32_t a){if(read_ops<12)fprintf(stderr,"read %08x\n",a);++read_ops;if(is_mmio(a)){if(a&3){fail("unaligned MMIO read");return 0;}return mmio_read(a-AUTONOMOUS_MMIO_BASE);}if(!range(a,4)){fail("CPU word read range");return 0;}return original.mem_read_w(r,a);}
static uint16_t read_half(riscv_t*r,uint32_t a){++read_ops;if(is_mmio(a)||!range(a,2)){fail("CPU half read range/MMIO");return 0;}return original.mem_read_s(r,a);}
static uint8_t read_byte(riscv_t*r,uint32_t a){++read_ops;if(is_mmio(a)||!range(a,1)){fail("CPU byte read range/MMIO");return 0;}return original.mem_read_b(r,a);}
static void write_word(riscv_t*r,uint32_t a,uint32_t v){if(write_ops<12)fprintf(stderr,"write %08x=%08x\n",a,v);++write_ops;if(is_mmio(a)){if(a&3){fail("unaligned MMIO write");return;}mmio_write(a-AUTONOMOUS_MMIO_BASE,v);return;}if(!range(a,4)){fail("CPU word write range");return;}original.mem_write_w(r,a,v);}
static void write_half(riscv_t*r,uint32_t a,uint16_t v){++write_ops;if(is_mmio(a)||!range(a,2)){fail("CPU half write range/MMIO");return;}original.mem_write_s(r,a,v);}
static void write_byte(riscv_t*r,uint32_t a,uint8_t v){++write_ops;if(is_mmio(a)||!range(a,1)){fail("CPU byte write range/MMIO");return;}original.mem_write_b(r,a,v);}
static uint32_t fetch(riscv_t*r,uint32_t a){static unsigned trace=0;if(trace++<12)fprintf(stderr,"fetch %08x\n",a);if(a<0x05000000||!range(a,4)||a>=0x05800000){fail("instruction fetch outside program reservation");return 0;}return original.mem_ifetch(r,a);}
static unsigned char *file(const char*path,size_t*n){FILE*f=fopen(path,"rb");if(!f)return NULL;if(fseek(f,0,SEEK_END)||ftell(f)<0){fclose(f);return NULL;}*n=(size_t)ftell(f);rewind(f);unsigned char*p=malloc(*n?*n:1);if(!p||fread(p,1,*n,f)!=*n){free(p);fclose(f);return NULL;}fclose(f);return p;}
static int load(uint32_t a,const void*p,size_t n){return n<=UINT32_MAX&&rv32emu_write_memory(vm,a,p,n)==RV32EMU_OK;}
static uint32_t u32(const unsigned char*p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint64_t u64(const unsigned char*p){return u32(p)|(uint64_t)u32(p+4)<<32;}
static uint32_t u16(const unsigned char*p){return (uint32_t)p[0]|(uint32_t)p[1]<<8;}
static uint64_t dirty_bss(const char*path){
 size_t n;unsigned char*p=file(path,&n);if(!p||n<52||memcmp(p,"\177ELF\1\1",6)){free(p);fail("ELF32 section table");return 0;}
 const uint32_t off=u32(p+32),size=u16(p+46),count=u16(p+48);uint64_t total=0;
 if(size<40||(uint64_t)off+(uint64_t)size*count>n){free(p);fail("ELF sections range");return 0;}
 unsigned char dirty[4096];memset(dirty,0xa5,sizeof dirty);
 for(unsigned i=0;i<count;i++){
  const unsigned char*s=p+off+i*size;const uint32_t type=u32(s+4),flags=u32(s+8),addr=u32(s+12),bytes=u32(s+20);
  if(type!=8||!(flags&2)||!bytes)continue;
  if(!range(addr,bytes)){fail("ELF BSS range");break;}
  for(uint32_t pos=0;pos<bytes;){const size_t take=bytes-pos<sizeof dirty?bytes-pos:sizeof dirty;if(!load(addr+pos,dirty,take)){fail("BSS prefill");break;}pos+=(uint32_t)take;}
  total+=bytes;
 }
 free(p);return total;
}
int main(int argc,char**argv){
 const int smoke=argc==7&&!strcmp(argv[6],"--smoke");
 if(argc!=6&&!smoke){fprintf(stderr,"usage: runner firmware.elf model.rqg RGB640.PPM output.f32 report.json [--smoke]\n");return 2;}
 size_t pn,in;unsigned char*p=file(argv[2],&pn),*image=file(argv[3],&in);if(!p||!image||pn<128||memcmp(p,"RQG2",4)){fprintf(stderr,"input files\n");return 2;}
 const uint32_t meta=u32(p+24),payload=u32(p+28),arena_bytes=u32(p+32),input=u32(p+16),arena=(65536+payload+4095)&~4095u,scratch=(arena+arena_bytes+4095)&~4095u;
 if((uint64_t)meta+payload!=pn||meta<128||(uint64_t)128+64*(input+1)>meta||scratch>=0x05000000){fprintf(stderr,"package layout\n");return 2;}
 /* Accept only the exact bounded P6 header generated by the SD preparation tool. */
 unsigned char*rgb=image;size_t header=0;for(unsigned lines=0;header<in&&lines<3;header++)if(image[header]=='\n')++lines;
 if(header>64||in-header!=640u*640u*3u||memcmp(image,"P6\n640 640\n255\n",15)){fprintf(stderr,"requires canonical RGB P6 640x640\n");return 2;}rgb+=header;
 rv32emu_options_t options;rv32emu_options_init(&options);options.memory_size=capacity;
 if(rv32emu_create(argv[1],&options,&vm)!=RV32EMU_OK){fprintf(stderr,"ELF create failed\n");return 2;}
 const uint64_t bss_dirty_bytes=dirty_bss(argv[1]);if(fault)return 2;
 struct AutonomousMailbox mb={0};mb.magic=AUTONOMOUS_MAGIC;mb.abi=AUTONOMOUS_ABI;mb.command=1;mb.token=1;mb.metadata_base=0x05800000;mb.metadata_bytes=meta;mb.constant_base=65536;mb.arena_base=arena;mb.scratch_base=scratch;mb.scratch_bytes=0x05000000-scratch;
 if(!load(mb.metadata_base,p,meta)||!load(mb.constant_base,p+meta,payload)||!load(0x05900000,rgb,640u*640u*3u)||!load(AUTONOMOUS_MAILBOX_BASE,&mb,sizeof mb)){fail("preload");return 2;}
 const uint64_t input_addr=arena+u64(p+128+input*64+40);fprintf(stdout,"input target 0x%08"PRIx64"; RV32 firmware performs RGB conversion\n",input_addr);free(p);free(image);
 riscv_io_t replacements={0};replacements.mem_ifetch=fetch;replacements.mem_read_w=read_word;replacements.mem_read_s=read_half;replacements.mem_read_b=read_byte;replacements.mem_write_w=write_word;replacements.mem_write_s=write_half;replacements.mem_write_b=write_byte;rv32emu_autonomous_install(vm,&replacements,&original);
 uint64_t slices=0;unsigned last_state=0,last_progress=UINT32_MAX;const time_t start=time(NULL);rv32emu_status_t st=RV32EMU_OK;
 while(!fault&&st==RV32EMU_OK){st=rv32emu_step(vm,1000000);++slices;rv32emu_read_memory(vm,AUTONOMOUS_MAILBOX_BASE,&mb,sizeof mb);
  if(mb.state!=last_state||mb.progress!=last_progress){fprintf(stdout,"state%u progress%u/%u nodes%u conv%u matrix%u tiles%"PRIu64" panels%"PRIu64" elapsed%ld\n",mb.state,mb.progress,mb.total,mb.nodes,mb.conv,mb.matmul,tiles,matrices,(long)(time(NULL)-start));fflush(stdout);last_state=mb.state;last_progress=mb.progress;}
  if(mb.state>=AP_COMPLETE)break;
  if(time(NULL)-start>10800){fail("ISA test deadline");break;}
 }
 int completed=!fault&&firmware_finished==1&&mb.state==AP_COMPLETE&&(smoke?(mb.nodes==14&&tiles==1&&matrices==1):(mb.nodes==649&&mb.conv==57&&mb.matmul==65&&mb.output_count==1800&&mb.completed_token==1))&&range(mb.output_base,(uint64_t)mb.output_count*4);
 if(completed){unsigned char out[7200];const size_t bytes=(size_t)mb.output_count*4;if(bytes>sizeof out||rv32emu_read_memory(vm,mb.output_base,out,bytes)!=RV32EMU_OK){fail("output read");completed=0;}else{FILE*f=fopen(argv[4],"wb");if(!f||fwrite(out,1,bytes,f)!=bytes){fail("output file");completed=0;}if(f)fclose(f);}}
 FILE*f=fopen(argv[5],"w");if(f){fprintf(f,"{\"execution_completed\":%s,\"hardware_access\":false,\"actual_RV32_instructions\":true,\"integer_accelerator_oracle\":true,\"F_extension_enabled\":false,\"BSS_prefilled_A5_bytes\":%"PRIu64",\"mailbox_state\":%u,\"error\":%u,\"progress\":%u,\"nodes\":%u,\"conv\":%u,\"matmul\":%u,\"tile_commands\":%"PRIu64",\"matrix_commands\":%"PRIu64",\"oracle_macs\":%"PRIu64",\"CPU_read_instructions\":%"PRIu64",\"CPU_write_instructions\":%"PRIu64",\"step_slices\":%"PRIu64",\"elapsed_host_seconds\":%ld,\"output_address\":%u,\"output_count\":%u}\n",completed?"true":"false",bss_dirty_bytes,mb.state,mb.error,mb.progress,mb.nodes,mb.conv,mb.matmul,tiles,matrices,macs,read_ops,write_ops,slices,(long)(time(NULL)-start),mb.output_base,mb.output_count);fclose(f);}
 fprintf(stdout,"ISA execution complete=%d error_text=%.96s\n",completed,mb.error_text);rv32emu_destroy(vm);return completed?0:1;
}

#pragma once
#include <cstdint>
#include <cstddef>
namespace inference { namespace npu_ddr {
struct Tile {
 unsigned ic=0,oc=0,oh=0,ow=0,kernel=0,stride=0;bool first=false,final=false;
 unsigned full_h=0,full_w=0;std::int32_t origin_y=0,origin_x=0;
 std::uint32_t input_base=0,input_row_pitch=0,input_channel_pitch=0,weight_base=0,weight_oc_stride=0,output_base=0,output_row_pitch=0,output_channel_pitch=0;
};
enum class CounterSampling {Full,Disabled};
struct Counters {std::uint64_t tx_us=0,rx_us=0,ready_wait_us=0,wire_bytes=0,kernel_cycles=0,ddr_wait_cycles=0,tile_jobs=0,read_bytes=0,write_bytes=0,cycle_samples=0;bool cycle_counters_valid=true;};
// Idle-only, explicit measurement policy. Full is the boot default. Disabled
// omits cycle-register queries only; zero cycle totals then mean unavailable.
// Phase/difference reporters must propagate validity and subtract samples.
bool configure_counter_sampling(CounterSampling);
CounterSampling counter_sampling();
// Process-local lease identity. Changes on every begin/end boundary, including
// failed setup. Read under the same serialized owner as other transport APIs.
std::uint64_t session_serial();
bool configure_timing(unsigned half_ns,unsigned setup_ns,unsigned guard_ns);
void get_timing(unsigned &half_ns,unsigned &setup_ns,unsigned &guard_ns);
bool begin();
bool self_test(unsigned &checked);
bool read(std::uint64_t address,void *data,std::size_t bytes);
bool write(std::uint64_t address,const void *data,std::size_t bytes);
bool tile(const Tile&);
bool unchanged();
void end();
const char*error();
Counters counters();
}}

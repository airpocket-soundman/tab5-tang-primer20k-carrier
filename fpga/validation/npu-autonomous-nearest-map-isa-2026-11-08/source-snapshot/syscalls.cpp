#include "platform.hpp"
#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <sys/stat.h>
extern "C" {
extern unsigned char __heap_start[],__heap_end[];
void *_sbrk(std::ptrdiff_t n){static auto p=reinterpret_cast<std::uintptr_t>(__heap_start);const auto start=reinterpret_cast<std::uintptr_t>(__heap_start),end=reinterpret_cast<std::uintptr_t>(__heap_end);if((n>=0&&std::uintptr_t(n)>end-p)||(n<0&&std::uintptr_t(-n)>p-start)){errno=ENOMEM;return reinterpret_cast<void*>(-1);}auto previous=p;p+=n;return reinterpret_cast<void*>(previous);}
int _write(int,const void*,unsigned n){return int(n);}int _read(int,void*,unsigned){return 0;}int _close(int){errno=EBADF;return -1;}int _fstat(int,struct stat*s){s->st_mode=S_IFCHR;return 0;}int _isatty(int){return 1;}int _lseek(int,int,int){return 0;}int _getpid(){return 1;}int _kill(int,int){errno=EINVAL;return -1;}
[[noreturn]] void _exit(int code){autonomous::fail(0x100u+unsigned(code),"firmware_exit");for(;;)asm volatile("":::"memory");}
}

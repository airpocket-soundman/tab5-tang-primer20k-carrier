#pragma once
#include "abi.h"
#include <cstdint>
#include <cstddef>
namespace autonomous {
inline volatile AutonomousMailbox& mailbox(){return *reinterpret_cast<volatile AutonomousMailbox*>(AUTONOMOUS_MAILBOX_BASE);}
inline std::uint32_t mmio(unsigned offset){return *reinterpret_cast<volatile std::uint32_t*>(AUTONOMOUS_MMIO_BASE+offset);}
inline void mmio(unsigned offset,std::uint32_t v){*reinterpret_cast<volatile std::uint32_t*>(AUTONOMOUS_MMIO_BASE+offset)=v;asm volatile("":::"memory");}
bool cancelled();
bool read(void*,std::uint64_t,void*,std::size_t);
bool write(void*,std::uint64_t,const void*,std::size_t);
void fail(unsigned,const char*);
}

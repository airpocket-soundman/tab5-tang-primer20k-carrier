# Tab5 FPGA Workstation — Modular Memory and Graphics Demonstrator

Prepared for EasyEDA Spark 2026, international program. Draft, not submitted.

## Project summary

Tab5 FPGA Workstation will combine an M5Stack Tab5, a Sipeed Tang Primer 20K Core, a custom carrier PCB, a protective enclosure, and demonstrator software into a working embedded system. It will investigate explicit use of FPGA-side DDR3 and hardware acceleration from a touchscreen computer.

The project targets a practical engineering problem: an ESP32-P4 system has limited working memory and processing resources, while an FPGA module provides configurable logic and its own DDR3. The carrier will provide power, a protected bidirectional parallel connection, user controls, and an experimental HDMI output. The completed system will demonstrate measured behavior rather than claim automatic memory expansion or unverified performance.

## Hardware scope

- Full-size125×78mm, four-layer carrier, retaining six mechanical mounting locations.
- Regulated12V barrel input and12V USB-C PD input.
- Independent5V converter for the FPGA Core; Tab5 receives HVIN. The Tab5 and Core5V rails are not tied together.
- Power-off bus isolation, monitoring of both supplies, and an initially open manual bus-arm jumper.
- Eight data lines plus clock, direction, ready, and auxiliary signals.
- A204-contact socket assembled by the manufacturer; the FPGA Core itself is supplied by the entrant.
- Manufacturer assembly of the HDMI connector, its19 signal contacts and four shell tabs, USB-C, small components, and supported controls. All103 populated board components have selected LCSC part numbers. The first quotation includes99 existing PCBA components plus the DC jack, bottom Tab5 header, bus-arm header and stop switch as wave-soldering candidates. If any assembly is declined, compatible selected parts will be bought directly from LCSC for hand soldering; this is excluded from expected sponsorship unless explicitly approved.
- A ventilated protective cover designed around the complete assembled system.

## Demonstration plan

The first working demonstration will show bidirectional transfers, CRC-checked DDR3 write/readback, and one small computation checked against a host reference. A graphics application will subsequently compare CPU rendering with a separate FPGA graphics configuration where feasible.

Linux memory experiments and the ESP-IDF graphics application use separate software and FPGA bitstreams. Simultaneous operation is not an initial requirement. FPGA DDR3 is an explicitly addressed external data store, not transparent Linux main memory. DMA throughput and graphics frame rate will be measured on the manufactured hardware.

## Current status and design provenance

Existing public project work includes KiCad carrier designs, engineering checks, software reference implementations, and FPGA development plans. The physical Tab5-to-FPGA link and complete application have not yet been validated on this carrier. We are preparing a separate full-size Spark edition while retaining the existing designs.

The current engineering reference is KiCad. It is not represented as an eligible EasyEDA-native entry. The revised carrier has been migrated to a separate EasyEDA Pro native project and is being cross-checked using identical equivalent-circuit analyses. Native data and a successful migration do not by themselves establish compliance with the program's100%-EasyEDA design requirement. Whether importing any existing design data is allowed requires the organizer's confirmation. All reused design material and its origin will be disclosed.

## Sponsorship request

The entrant will purchase the Tab5 and Tang Primer20K Core modules separately and exclude them from the requested support.

The proposed first manufacturing request is five carrier PCBs with two assemblies, subject to current program approval and a finalized, itemized quotation. The quotation will include the Core socket, USB-C and HDMI connectors, circuit components, and as much manufacturer assembly as supported. Enclosure printing may be requested separately after its mechanical design is checked.

The final requested amount will come from unpaid manufacturer quotations. No award prize or completion coupon is counted as initial development funding. Standalone LCSC purchases are excluded from expected Spark support unless explicitly approved; current official responses distinguish them from JLCPCB manufacturing coupons.

## Planned open deliverables

- Complete eligible EasyEDA project files, schematic, PCB, libraries, and assembly data.
- Enclosure source files and assembly instructions.
- Links to Linux and ESP-IDF software, FPGA sources, and exact tested revisions, with license information.
- Photographs and a video showing the assembled enclosed system operating.
- Power measurements, transfer integrity results, DDR3 tests, and a reproducible reference-comparison demo.
- Clear separation of measured results, simulations, design assumptions, and future work.

## Existing repositories

- Carrier: https://github.com/airpocket-soundman/tab5-tang-primer20k-carrier
- Linux: https://github.com/airpocket-soundman/tab5-linux-fpga
- Memory research: https://github.com/airpocket-soundman/esp32p4-linux-fpga-memory
- Graphics: https://github.com/airpocket-soundman/tab5-fpga-gpu

## Minimum completion and further goals

Minimum completion is an enclosed, reproducibly operating system with safe power sequencing, bidirectional transfers, DDR3 integrity checks, and one demonstrated offload operation. Sustained DMA performance, large-memory application examples, FPGA rendering, and HDMI output are subsequent goals whose results will be reported honestly. If this minimum system does not satisfy the program's complete-product criterion, the scope will be clarified with the organizer before requesting support.

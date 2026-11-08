# Independent RUN lease control proof

13 cases /57 assertions pass against the current unmodified run-control RTL. A deliberately unguarded START copy fails the same-edge START+ABORT assertion, demonstrating that the test catches the reviewed defect.

Coverage: readiness (calibration/CPU/arbiter/MAC), START+ABORT rejection, fault/trap gating, latest monitor fields/cycles, ignored CLEAR/reSTART while RUN, delayed CPU/DDR/MAC drain, same-edge FINISH versus ABORT/epoch/calibration loss, sticky trap/code/error, unsafe abort/quarantine owner retention, coordinated ARM reset. This unit does not prove complete core integration, DDR timing, resource fit or physical hardware.

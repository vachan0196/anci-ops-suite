`tsc-after-h171-h173.txt` is empty by design.

It captures the output of `npx tsc --noEmit` run in `apps/web` after the H171
and H173 changes. The command exited 0. TypeScript prints nothing on a clean
run, so an empty file is a successful capture, not a missing one.

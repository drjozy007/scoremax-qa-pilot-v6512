# Single-CPU HTTP execution qualification

The exact V13 runtime remains unchanged. Four HTTP threads share the existing one-CPU service. Repeated mixed-load failures are retained; no latency target, operation count, source image, native write, backup or integrity assertion is reduced. The proposed correction is one HTTP worker with one HTTP thread on the same service. Existing background services and stable secret loading stay intact.

Local one-thread measurement used 6.85 CPU-seconds for400successful requests while preserving native signed writes, images, duplicate handling, exact withdrawal and consistent backup; local p95 was1190.966567ms. The prior hosted four-thread comparison took10.19 CPU-seconds and failed at1511.834613ms. These are separate environments and are not a paired causal estimate.

The existing workflow retains the four-thread diagnostic with its actual outcome and adds strict one-thread zero-extra-index acceptance on all four routes at1/10/50 learners plus the unchanged400GET/50-concurrent mixed test and1500ms gate. Only a passed proposed topology can be considered for cutover; hosted success alone is not Render acceptance. No production configuration has changed.

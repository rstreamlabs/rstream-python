# Changelog

## [0.6.1](https://github.com/rstreamlabs/rstream-python/compare/v0.6.0...v0.6.1) (2026-08-15)


### Bug Fixes

* **release:** validate Python package metadata ([3334245](https://github.com/rstreamlabs/rstream-python/commit/3334245a09f2826ccd970df432f3a03d2af3d577))
* **release:** validate Python package metadata ([b4cdea5](https://github.com/rstreamlabs/rstream-python/commit/b4cdea5d8acc147545daf3a977d1991f80069060))

## [0.6.0](https://github.com/rstreamlabs/rstream-python/compare/v0.5.0...v0.6.0) (2026-08-15)


### Features

* **runtime:** negotiate bounded control liveness ([8f41108](https://github.com/rstreamlabs/rstream-python/commit/8f41108c7f57d837e605c5156a8046bc6fc25603))
* **runtime:** negotiate bounded control liveness ([0e39636](https://github.com/rstreamlabs/rstream-python/commit/0e396369421a8f023f3fc42a78a68c9240309201))


### Bug Fixes

* **runtime:** parallelize bounded proxy handshakes ([397f0cd](https://github.com/rstreamlabs/rstream-python/commit/397f0cdd0fda7329bf709f331ee0408551118e02))
* **runtime:** preserve payloads across control loss ([37cfd47](https://github.com/rstreamlabs/rstream-python/commit/37cfd474dc1d4fc1ebfca58e9260b1506bd92f27))

## [0.5.0](https://github.com/rstreamlabs/rstream-python/compare/v0.4.0...v0.5.0) (2026-08-01)


### Features

* **edge:** release region-aware Python tunnels ([61250d2](https://github.com/rstreamlabs/rstream-python/commit/61250d2750d090434d01eee1c1da3495c348506b))
* **edge:** support region-aware tunnels ([095356a](https://github.com/rstreamlabs/rstream-python/commit/095356a17d6a841d460f82453c837e8e3b4b3b45))


### Bug Fixes

* **api:** align project routing metadata ([1f7d26a](https://github.com/rstreamlabs/rstream-python/commit/1f7d26a7de428e6e6a32c8fac523858626927f85))
* **edge:** allow cross-region routing for every protocol ([7626e8d](https://github.com/rstreamlabs/rstream-python/commit/7626e8dc0f815182393d423a09add57333673c31))


### Documentation

* organize internal documentation ([b46829d](https://github.com/rstreamlabs/rstream-python/commit/b46829d97e05403cb5c4b24260a8701bc1f9b509))

## [0.4.0](https://github.com/rstreamlabs/rstream-python/compare/v0.3.0...v0.4.0) (2026-07-18)


### Features

* add published TCP tunnels ([f1b2e89](https://github.com/rstreamlabs/rstream-python/commit/f1b2e89d1a5baf26b13b72e069c982335d7af934))

## [0.3.0](https://github.com/rstreamlabs/rstream-python/compare/v0.2.0...v0.3.0) (2026-07-11)


### Features

* add automatic transport and datagram delivery metadata ([344a6f2](https://github.com/rstreamlabs/rstream-python/commit/344a6f2d27a00090fe40df8a3ecb70eceadf2524))

## [0.2.0](https://github.com/rstreamlabs/rstream-python/compare/v0.1.1...v0.2.0) (2026-06-25)


### Features

* add engine API watch and stable domains support ([eb41f8c](https://github.com/rstreamlabs/rstream-python/commit/eb41f8c20babfa3222d8510e5e49d2cc97ede221))

## [0.1.1](https://github.com/rstreamlabs/rstream-python/compare/v0.1.0...v0.1.1) (2026-06-16)


### Bug Fixes

* handle asyncio timeouts on Python 3.10 ([a645485](https://github.com/rstreamlabs/rstream-python/commit/a645485de5285424eba983fd85675d13379d6aad))

## 0.1.0

- Initial Python SDK for rstream bytestream tunnels.
- Added async runtime client, control channel, tunnel creation, private dial,
  local forwarding, ASGI helper, shared config resolution, webhook signature
  verification, tests, examples, and CI.

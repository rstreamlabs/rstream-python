# Handle TLS stream shutdown consistently

A peer closing during an exchange can surface `APPLICATION_DATA_AFTER_CLOSE_NOTIFY` through asyncio. Reproduce the close sequence and define which outcomes are clean end-of-stream. Preserve truncated-data and protocol errors; do not suppress SSL failures generally. Cover reads, writes, cancellation and repeated close before changing the mapping.

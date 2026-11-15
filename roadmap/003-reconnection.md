# Define automatic reconnection

Applications currently rebuild control channels and tunnels after an engine connection is lost, and restart interrupted watch streams themselves. Add an explicit retry policy with bounded backoff, cancellation and deterministic shutdown. Preserve tunnel identity and endpoint behavior, and test engine restarts and failed authorization without replaying operations unsafely.

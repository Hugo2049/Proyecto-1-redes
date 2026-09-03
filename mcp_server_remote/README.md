# Clinic Appointment MCP Server, Remote, Cloudflare Workers

This is the same Clinic Appointment MCP server as [`mcp_server_v1`](../mcp_server_v1), deployed to run remotely on [Cloudflare Workers](https://workers.cloudflare.com/) instead of running as a local stdio process, this covers functionality 6 of the project statement. The JSON-RPC 2.0 handling in [`src/index.js`](src/index.js) is a line by line JavaScript version of `mcp_server_v1/main.py`, same tools, same parameters, same responses, written by hand, no MCP SDK.

**Live endpoint:** `https://clinic-appointment-mcp-remote.hugomcp.workers.dev/`

## Transport, HTTP instead of stdio

The local server sends JSON-RPC messages over stdin and stdout, one per line. Workers cannot run a long lived stdio process, so the remote version exposes a single HTTP endpoint instead:

- `POST /` with a JSON-RPC 2.0 message in the body, returns a JSON-RPC 2.0 response in the body, for `initialize`, `tools/list` and `tools/call`.
- Notifications, like `notifications/initialized`, which have no `id`, get an empty `202 Accepted`.
- `GET /` returns a plain text banner, useful as a health check.

## Tools

Same as the local server, see [`mcp_server_v1/README.md`](../mcp_server_v1/README.md#tools) for the full table of parameters, `list_specialties`, `list_doctors`, `check_availability`, `book_appointment`, `cancel_appointment`, `reschedule_appointment`.

## Deploying

You need a free [Cloudflare account](https://dash.cloudflare.com/sign-up) with a registered `workers.dev` subdomain, this is a one time setup done from Workers and Pages, Subdomain, plus Node.js and `wrangler`, which gets installed on demand through `npx`.

```bash
cd mcp_server_remote
npx wrangler login      # opens a browser to log in
npx wrangler deploy
```

`wrangler deploy` prints the live URL, update `CLINIC_REMOTE_URL` in `chatbot/.env` if it is different from the default.

To test locally before deploying, run `npx wrangler dev`, this runs the same Worker code on your computer, it was used during development to check all 6 tools and the error handling before publishing.

## Known limitations

- State does not last. The data lives in variables inside the Worker, and those only stay around while that instance of the Worker stays warm. A cold start, for example after being idle, or a request handled by a different edge location, resets the specialties and doctors back to the sample data, and clears any appointments made before. A real production setup would store this in Workers KV or a Durable Object, that is outside the scope of this project.
- Free plan limits, 100,000 requests a day, 10 milliseconds of CPU time per request, which is far more than this project needs.
- A few networking details showed up while testing, worth mentioning here since they also matter for the Wireshark and report sections:
  - Cloudflare answered with a 403 error to requests without a browser style User-Agent header, so the chatbot's HTTP client, `chatbot/src/chatbot/mcp_http_client.py`, always sends one.
  - The network used during development intercepts TLS traffic, and every so often that produced broken certificates, missing authority key identifier. Using the operating system's certificate store instead of the bundled one, through the `truststore` package, plus a short retry, fixed this.

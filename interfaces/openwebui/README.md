# Open WebUI Interface

This directory contains the Open WebUI pipeline interface for the alpha_berkeley framework.

## Troubleshooting

### Pipelines Not Appearing After Container Restart

**Symptom**: After running `./scripts/local-dev.sh up`, the Open WebUI interface shows an empty pipeline list (no "Otter", "Arena Model", or other configured applications).

**Root Cause**: This is a known upstream issue in Open WebUI ([Issue #111](https://github.com/open-webui/pipelines/issues/111)) where the frontend caches the model/pipeline list and doesn't automatically refresh when the pipelines container restarts. The pipelines themselves ARE loading correctly on the backend - the issue is purely frontend cache-related.

### Workaround

There are two simple ways to trigger the frontend to refresh:

#### Option 1: Manual Refresh via Settings (Recommended)

1. Open Open WebUI in your browser
2. Navigate to **Settings** (gear icon)
3. Go to **Pipelines** section
4. Click **SAVE** (even without making any changes)
5. The pipeline list should now refresh and show all available applications

#### Option 2: Trigger via CLI

1. Run any CLI command (e.g., `alpha-berkeley`)
2. Refresh your browser
3. The pipeline list should now appear in Open WebUI

The CLI approach works because it triggers the pipeline discovery mechanism which forces a refresh.

### Verifying Pipeline Server Status

If the workarounds above don't work, you can verify that the pipeline server is running correctly:

```bash
# Check if pipelines container is running
/opt/podman/bin/podman ps | grep pipelines

# Check pipeline server logs
/opt/podman/bin/podman logs pipelines

# Verify pipeline endpoints are accessible (from host)
curl -H "Authorization: Bearer 0p3n-w3bu!" http://localhost:9099/pipelines
curl -H "Authorization: Bearer 0p3n-w3bu!" http://localhost:9099/v1/models
```

If these commands show errors, there may be an actual server issue. Check the container logs for details.

### Expected Behavior

- **Backend**: Pipelines load immediately when container starts (lazy module loading on first request)
- **Frontend**: Cache may show stale/empty list until manually refreshed
- **After workaround**: All configured applications should appear in the pipeline dropdown

### Related Issues

- Upstream Open WebUI issue: https://github.com/open-webui/pipelines/issues/111
- Partial fix merged in PR #210, but issue persists for custom pipelines

### Notes for Developers

This is an upstream Open WebUI limitation, not a bug in the alpha_berkeley framework. The framework correctly:
- Loads all pipeline modules at container startup
- Exposes them via the standard OpenAI-compatible API endpoints
- Registers them with the Open WebUI backend

The frontend simply needs a manual refresh trigger after container restarts. Future versions of Open WebUI may address this automatically.

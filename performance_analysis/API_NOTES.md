# Bybit API Integration Notes

## API Limitations & Solutions

### 7-Day Time Range Limit

**Issue**: Bybit's `/v5/position/closed-pnl` endpoint limits the time range between `startTime` and `endTime` to 7 days maximum.

**Solution**: The script automatically detects when a requested period exceeds 7 days and splits it into multiple 7-day chunks.

**Example Output**:
```
📅 Time range exceeds 7 days, splitting into chunks...
   Chunk 1: 2025-09-01 to 2025-09-08
   Chunk 2: 2025-09-08 to 2025-09-15
   Chunk 3: 2025-09-15 to 2025-09-22
   Chunk 4: 2025-09-22 to 2025-09-29
   Chunk 5: 2025-09-29 to 2025-10-06
✅ Fetched total of 125 records across 5 chunks
```

### Implementation Details

1. **Chunk Calculation**:
   ```python
   MAX_RANGE_MS = 7 * 24 * 60 * 60 * 1000  # 7 days in milliseconds
   ```

2. **Automatic Splitting**:
   - Detects if time range > 7 days
   - Splits into 7-day windows
   - Fetches each chunk sequentially
   - Combines all results

3. **Rate Limiting**:
   - 0.2s delay between chunks
   - 0.1s delay between pagination requests
   - Prevents hitting API rate limits

### API Endpoints Used

**Position Closed P&L**: `/v5/position/closed-pnl`
- Fetches closed position P&L records
- Supports pagination via cursor
- Max 50 records per request (configurable)
- **Time limit**: 7 days max per request

**Market Time**: `/v5/market/time`
- Gets Bybit server time for signature
- Used for timestamp synchronization
- Cached for 5 minutes to reduce calls

### Authentication

**Signature Method**: HMAC SHA256

**Signature String Format**:
```
timestamp + apiKey + recvWindow + queryString
```

**Important**: Parameter order matters! Don't sort parameters.

**Headers Required**:
- `X-BAPI-API-KEY`: Your API key
- `X-BAPI-SIGN`: HMAC SHA256 signature
- `X-BAPI-SIGN-TYPE`: "2" (SHA256)
- `X-BAPI-TIMESTAMP`: Server timestamp in milliseconds
- `X-BAPI-RECV-WINDOW`: Request validity window (10000ms)

### Pagination

Bybit uses cursor-based pagination:
1. First request returns data + `nextPageCursor`
2. Subsequent requests include `cursor` parameter
3. Continue until `nextPageCursor` is empty

**Example**:
```python
cursor = None
while True:
    params = {"category": "linear", "limit": "50"}
    if cursor:
        params["cursor"] = cursor
    
    response = fetch_data(params)
    data.extend(response["list"])
    
    cursor = response.get("nextPageCursor", "")
    if not cursor:
        break
```

### Error Handling

**Common Errors**:

1. **"error sign!"**
   - Cause: Invalid signature
   - Fix: Ensure parameters aren't sorted, use correct timestamp

2. **"The time range between startTime and endTime cannot exceed 7 days"**
   - Cause: Time range > 7 days
   - Fix: Automatically handled by chunking

3. **"Invalid timestamp"**
   - Cause: Clock skew between local and server
   - Fix: Uses server time with offset caching

### Performance Optimizations

1. **Time Offset Caching**:
   - Calculates server-local time offset
   - Caches for 5 minutes
   - Reduces server time API calls

2. **Chunked Fetching**:
   - Only splits when necessary (> 7 days)
   - Shows progress for long-running requests
   - Combines results efficiently

3. **Rate Limiting**:
   - Built-in delays prevent 429 errors
   - Respects Bybit's rate limits
   - Configurable timeout settings

## API Documentation Reference

Official Bybit API v5 Documentation:
- Position Closed P&L: https://bybit-exchange.github.io/docs/v5/position/close-pnl
- Authentication: https://bybit-exchange.github.io/docs/v5/guide#authentication
- Rate Limits: https://bybit-exchange.github.io/docs/v5/rate-limit

## Testing

**Test with Demo Account**:
```bash
# Set in .env
BYBIT_USE_DEMO=True
BYBIT_API_KEY=your_demo_key
BYBIT_API_SECRET=your_demo_secret
```

**Test Different Periods**:
```bash
# 1 week (no chunking)
python performance_analysis/analyze_performance.py --period 1w

# 1 month (chunked into ~4 requests)
python performance_analysis/analyze_performance.py --period 1m

# Custom 2 months (chunked into ~8 requests)
python performance_analysis/analyze_performance.py --period 2025-08-01:2025-10-01
```

## Future Enhancements

- [ ] Parallel chunk fetching for faster performance
- [ ] Progress bar for long-running requests
- [ ] Retry logic for failed chunks
- [ ] Caching of fetched data to avoid re-fetching
- [ ] Support for other Bybit endpoints (trade history, order history)

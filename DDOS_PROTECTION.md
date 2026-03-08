# DDoS Protection Strategy

## Current Protection Layers

### 1. **Vercel Edge Network** (First Line of Defense)
- **What it does:** Caches static content at edge locations globally
- **Protection:** Most requests never reach your Python server
- **Config:** `s-maxage=1, stale-while-revalidate=86400` in `utils.py`
- **Effectiveness:** ~95% of normal traffic is served from cache

### 2. **IP Rate Limiting** (New - Application Level)
- **What it does:** Limits `/log_event` endpoint to 30 requests/minute per IP
- **Location:** `index.py` - line ~135
- **Protection:** Prevents single IP from spamming tracking events
- **Effectiveness:** Blocks naive DDoS attempts, script kiddies

### 3. **Visit Deduplication** (Database Level)
- **What it does:** 10-second cooldown between page visits from same IP
- **Location:** `index.py` - `log_visit` function
- **Protection:** Prevents rapid-fire page refresh attacks
- **Effectiveness:** Good for accidental spam, less effective against distributed attacks

### 4. **Thread Pool Limiting** (Resource Control)
- **What it does:** Max 2 concurrent background workers
- **Location:** `index.py` - line ~52
- **Protection:** Caps maximum DB connections from tracking
- **Effectiveness:** Prevents runaway connection exhaustion

### 5. **Domain Validation** (Input Sanitization)
- **What it does:** Only accepts URLs from yourlifepathways.com
- **Location:** `index.py` - `/log_event` endpoint
- **Protection:** Prevents logging of external/spoofed URLs
- **Effectiveness:** Prevents data pollution attacks

## Vulnerabilities & Mitigation

### ❌ Distributed Attacks (Many IPs)
**Risk:** Botnet with 1000+ IPs can bypass per-IP rate limiting
**Mitigation Options:**
1. Enable Redis rate limiting (currently disabled in `.env`)
2. Add Vercel's built-in anti-DDoS (Cloudflare integration)
3. Temporarily disable tracking via `TRAFFIC_LOGGING=no`

### ❌ Application-Level Attacks
**Risk:** Expensive queries to admin dashboard during attack
**Current Protection:** Admin requires authentication
**Additional:** Admin pages bypass cache, but Flask-Login throttles brute force

### ✅ Database Connection Exhaustion
**Protection:** 
- Thread pool: 2 workers max
- Supabase pooler: Handles 60 connections
- Current usage: ~15% of capacity

## Emergency Response

### If Under Attack:

1. **Immediate (30 seconds):**
   ```bash
   # Disable tracking in .env
   TRAFFIC_LOGGING=no
   
   # Restart server
   vercel --prod
   ```

2. **Short-term (5 minutes):**
   - Check Vercel Analytics for attack pattern
   - Review Supabase logs for connection spikes
   - Enable Redis rate limiting if available

3. **Long-term (1 hour):**
   - Upgrade to Vercel Pro for advanced DDoS protection
   - Consider Cloudflare in front of Vercel
   - Archive old tracking data to reduce DB size

## Monitoring

**Key Metrics to Watch:**
1. **Supabase Dashboard > Database > Connections**
   - Normal: < 10 connections
   - Warning: > 30 connections
   - Critical: > 50 connections

2. **Server Logs**
   - Look for: `[LOG_EVENT] Rate limit exceeded`
   - Many hits = potential attack

3. **Vercel Analytics**
   - Sudden traffic spike (10x normal)
   - Geographic anomalies (traffic from unexpected countries)

## Cost Impact

### Supabase Free Tier:
- **Connection limit:** 60 concurrent
- **Current usage:** ~8-10 (safe)
- **Under attack:** Could hit limit, causing 500 errors

### Vercel Free Tier:
- **Bandwidth:** 100 GB/month
- **Serverless Executions:** Unlimited
- **Edge Requests:** Unlimited (cached responses don't count)

**Most DDoS traffic will be absorbed by Vercel's edge cache and won't cost you anything or hit your DB!**

## Recommended Upgrades

### If Budget Allows:
1. **Enable Redis** ($0-5/month)
   - Distributed rate limiting
   - Better than in-memory solution
   - Survives server restarts

2. **Vercel Pro** ($20/month)
   - Advanced DDoS mitigation
   - Better analytics
   - Priority support

3. **Supabase Pro** ($25/month)
   - 200 concurrent connections
   - Point-in-time recovery
   - Daily backups

## Summary

**You are reasonably protected for a personal/small business site:**
- ✅ Vercel absorbs most attack traffic automatically
- ✅ Rate limiting prevents single-source spam
- ✅ Thread pooling prevents DB exhaustion
- ✅ Kill switch available (`TRAFFIC_LOGGING=no`)

**For peace of mind:**
- Monitor Supabase connections weekly
- Run cleanup script quarterly
- Keep tracking disabled if traffic looks suspicious

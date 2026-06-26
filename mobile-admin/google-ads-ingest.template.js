/**
 * RigaCap — Google Ads → admin-app ingest (TEMPLATE).
 *
 * A first-party Google Ads Script (Tools & Settings → Bulk Actions → Scripts →
 * + New script). Runs INSIDE Google Ads authenticated as the account — no API
 * developer token, no OAuth. Pulls per-campaign stats and POSTs them to the
 * RigaCap admin backend, which stores the snapshot and serves it to the phone
 * app's Ads tab.
 *
 * SETUP:
 *   1. Paste this into a new Ads Script.
 *   2. Replace INGEST_SECRET with the real value (kept out of git — ask Erik /
 *      see the live ADS_INGEST_SECRET env on the API Lambda).
 *   3. Authorize, Preview (check the log shows "200"), then Run.
 *   4. Schedule it: frequency = Hourly.
 */

var INGEST_URL = 'https://api.rigacap.com/api/admin/ads/ingest';
var INGEST_SECRET = 'PASTE_ADS_INGEST_SECRET_HERE';
var DATE_RANGE = 'LAST_30_DAYS'; // TODAY | YESTERDAY | LAST_7_DAYS | LAST_30_DAYS | THIS_MONTH

function main() {
  var totals = { spend: 0, clicks: 0, impressions: 0, conversions: 0 };
  var campaigns = [];

  var it = AdsApp.campaigns().get();
  while (it.hasNext()) {
    var c = it.next();
    var s = c.getStatsFor(DATE_RANGE);
    var spend = s.getCost();          // account currency, e.g. 304.72
    var clicks = s.getClicks();
    var impressions = s.getImpressions();
    var conversions = s.getConversions();
    if (spend === 0 && clicks === 0 && impressions === 0) continue; // skip dead campaigns
    campaigns.push({
      name: c.getName(),
      spend: spend,
      clicks: clicks,
      impressions: impressions,
      conversions: conversions,
    });
    totals.spend += spend;
    totals.clicks += clicks;
    totals.impressions += impressions;
    totals.conversions += conversions;
  }

  var payload = {
    spend: totals.spend,
    clicks: totals.clicks,
    impressions: totals.impressions,
    conversions: totals.conversions,
    cpc: totals.clicks > 0 ? totals.spend / totals.clicks : 0,
    date_range: DATE_RANGE,
    campaigns: campaigns,
  };

  var resp = UrlFetchApp.fetch(INGEST_URL, {
    method: 'post',
    contentType: 'application/json',
    headers: { 'X-Ads-Ingest-Secret': INGEST_SECRET },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });
  Logger.log('Ingest ' + resp.getResponseCode() + ': ' + resp.getContentText());
}

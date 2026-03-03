import React, { useState, useEffect, useCallback } from 'react';
import { Share2, Check, X, RefreshCw, Trash2, Image, MessageSquare, TrendingUp, BarChart3, Globe, Send, Plus, Edit3, Save, Power, Rocket, ChevronDown, ChevronUp, Sparkles, Clock, Ban, Calendar } from 'lucide-react';

import { formatDate } from '../utils/formatDate';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PLATFORMS = [
  { id: 'all', label: 'All' },
  { id: 'twitter', label: 'Twitter/X' },
  { id: 'instagram', label: 'Instagram' },
  { id: 'threads', label: 'Threads' },
];

const STATUSES = [
  { id: 'all', label: 'All' },
  { id: 'draft', label: 'Draft' },
  { id: 'approved', label: 'Approved' },
  { id: 'scheduled', label: 'Scheduled' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'posted', label: 'Posted' },
  { id: 'cancelled', label: 'Cancelled' },
];

const POST_TYPES = [
  { id: 'all', label: 'All' },
  { id: 'trade_result', label: 'Trade Result' },
  { id: 'missed_opportunity', label: 'Missed Opportunity' },
  { id: 'weekly_recap', label: 'Weekly Recap' },
  { id: 'regime_commentary', label: 'Regime' },
  { id: 'contextual_reply', label: 'Replies' },
  { id: 'instagram_comment_reply', label: 'IG Comments' },
  { id: 'manual', label: 'Manual' },
];

const STATUS_COLORS = {
  draft: 'bg-gray-100 text-gray-700',
  approved: 'bg-green-100 text-green-700',
  scheduled: 'bg-amber-100 text-amber-700',
  rejected: 'bg-red-100 text-red-700',
  posted: 'bg-blue-100 text-blue-700',
  cancelled: 'bg-red-50 text-red-400',
};

const TYPE_COLORS = {
  trade_result: 'bg-emerald-100 text-emerald-700',
  missed_opportunity: 'bg-amber-100 text-amber-700',
  weekly_recap: 'bg-purple-100 text-purple-700',
  regime_commentary: 'bg-sky-100 text-sky-700',
  contextual_reply: 'bg-cyan-100 text-cyan-700',
  instagram_comment_reply: 'bg-pink-100 text-pink-700',
  manual: 'bg-indigo-100 text-indigo-700',
};

const TYPE_LABELS = {
  trade_result: 'Trade Result',
  missed_opportunity: 'Missed Opportunity',
  weekly_recap: 'Weekly Recap',
  regime_commentary: 'Regime',
  contextual_reply: 'Reply',
  instagram_comment_reply: 'IG Comment',
  manual: 'Manual',
};

// Circular RigaCap logo SVG as inline component
function RigaCapLogo({ size = 40, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 -128 1280 1280" className={className}>
      <g transform="matrix(5.266369152845155 0 0 5.266369152845155 639.7474324688749 511.4611892669334)">
        <g>
          <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -22.37905439059665 -28.76675371508702)">
            <path fill="#67B3E9" d="M 215.4926147 348.1326294 C 215.4926147 341.4343262 220.5519104 335.9767151 227.0464782 335.2184448 L 241.64198299999998 278.3557434 C 238.3174896 275.98690799999997 236.13209529999997 272.1211853 236.13209529999997 267.7279358 C 236.13209529999997 260.5114746 241.98225399999998 254.66130070000003 249.19871519999998 254.66130070000003 C 255.88706969999998 254.66130070000003 261.3387146 259.70529180000005 262.1099243 266.18612670000005 L 309.18218989999997 278.15957640000005 C 311.5494384 274.8219604 315.4248962 272.62802120000003 319.82827749999996 272.62802120000003 C 323.99932849999993 272.62802120000003 327.67044059999995 274.6184387 330.06295769999997 277.6614685 L 391.39083859999994 258.8470459 C 391.8676757999999 252.0640717 397.4616393999999 246.6927338 404.36566159999995 246.6927338 C 405.08795159999994 246.6927338 405.78381349999995 246.79251100000002 406.47412109999993 246.9051972 L 420.4002074999999 223.132248 C 395.4410094999999 205.1961365 364.83840939999993 194.61979680000002 331.7564086999999 194.61979680000002 C 247.7547149999999 194.61979680000002 179.6581725999999 262.7163392 179.6581725999999 346.71804810000003 C 179.6581725999999 357.0606384 180.7147979999999 367.15197750000004 182.68611139999987 376.91201780000006 L 216.05313109999986 351.71652220000004 C 215.7245789 350.5704346 215.4926147 349.3842468 215.4926147 348.1326294 z"/>
          </g>
          <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -11.05489640960161 -8.986830154000359)">
            <path fill="#3298E2" d="M 427.8859863 228.8635559 L 414.53790280000004 251.6500549 C 416.32159420000005 253.88394159999999 417.43228150000004 256.67834469999997 417.43228150000004 259.75936889999997 C 417.43228150000004 266.9758301 411.58212280000004 272.82598879999995 404.36566160000007 272.82598879999995 C 400.1946106000001 272.82598879999995 396.5232849000001 270.83538819999995 394.13079830000004 267.7923279 L 332.80288690000003 286.60696409999997 C 332.3262634 293.38973999999996 326.73229970000006 298.7614746 319.8282775 298.7614746 C 313.1401366 298.7614746 307.68869010000003 293.7178955 306.9169005 287.23745729999996 L 259.8444213 275.2633972 C 257.7556457 278.2080688 254.4786376 280.2024536 250.71150200000002 280.6423034 L 236.11599720000004 337.5046081 C 239.44068900000005 339.8734741 241.62588490000005 343.7393798 241.62588490000005 348.13262929999996 C 241.62588490000005 355.34927359999995 235.77590930000005 361.19924919999994 228.55924980000003 361.19924919999994 C 226.02284230000004 361.19924919999994 223.67565910000002 360.44515979999994 221.67153920000004 359.19454949999994 L 185.03727710000004 386.8588560999999 C 189.38798510000004 402.7608335999999 196.24627670000004 417.6278685999999 205.16970810000004 431.00256339999993 L 343.5092162 312.1214903999999 L 408.03659050000005 312.1214903999999 L 465.59317010000007 274.40634149999994 C 456.0913391 256.8570251 443.2310181 241.3963165 427.8859863 228.8635559 z"/>
          </g>
          <g transform="matrix(0.447842401165958 0 0 0.447842401165958 73.82936460708436 -37.11089695025285)">
            <polygon fill="#172554" points="-45.30519105000002,-14.32876589999998 45.30519104999996,-39.44079589999998 -12.74574285,39.44079590000001 -17.06205755000002,3.2839356000000066"/>
          </g>
          <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -48.16632626991975 25.662112400608095)">
            <path fill="#172554" d="M 297.690155 513.3757935 C 291.8544922 512.1848145 286.1323242 510.6825867 280.5290222 508.9088135 L 280.5290222 405.3008118 L 233.16218569999998 446.0053406 L 233.16218569999998 485.1845703 C 189.93139649999998 454.3132019 161.66641239999998 403.77075190000005 161.66641239999998 346.71844480000004 C 161.66641239999998 321.47900390000007 167.2343445 297.52935790000004 177.14006049999998 275.9688110000001 L 153.41162119999998 275.9688110000001 C 144.68853769999998 297.8789672000001 139.83914199999998 321.7362060000001 139.83914199999998 346.71844480000004 C 139.83914199999998 452.54183960000006 225.93339549999996 538.6345215 331.7568056 538.6345215 C 336.23214740000003 538.6345215 340.6571657 538.4249878 345.0569765 538.1221314000001 L 345.0569765 349.8493347 L 297.69015520000005 390.5536499 L 297.69015520000005 513.3757935 z"/>
          </g>
          <g transform="matrix(0.447842401165958 0 0 0.447842401165958 41.62493388227972 31.445543033824293)">
            <path fill="#172554" d="M 523.1578979 333.3830872 L 501.27337639999996 333.3830872 C 501.617218 337.78863529999995 501.8457946 342.22619629999997 501.8457946 346.71844489999995 C 501.8457946 380.9995423 491.63201899999996 412.92395029999994 474.11251819999995 439.65051279999994 L 474.11251819999995 304.23995979999995 L 426.74587999999994 335.27807629999995 L 426.74587999999994 487.65298469999993 C 421.24215689999994 491.3716430999999 415.51919539999994 494.78399669999993 409.5847471999999 497.85028079999995 L 409.5847471999999 341.7442017 L 362.217926 341.7442017 L 362.217926 536.1913453 C 453.612976 521.5502931 523.6730957 442.17498789999996 523.6730957 346.7184449 C 523.6730957 342.2309875 523.4624023 337.7946167 523.1578979 333.3830872 z"/>
          </g>
          <g transform="matrix(0.447842401165958 0 0 0.447842401165958 -11.758155759779243 -60.819370702594256)">
            <path fill="#172554" d="M 331.7522278 169.315979 C 390.4548645 169.315979 442.57946780000003 197.9828644 474.8894653 242.0440826 L 483.06436149999996 239.7783813 C 449.4578552 192.3684234 394.1588134 161.3654937 331.75222769999993 161.3654937 C 258.06015009999993 161.3654937 194.28051749999995 204.5952758 164.42543019999994 267.0239257 L 173.28724659999995 267.0239257 C 202.5275574 209.120697 262.5750122 169.315979 331.7522278 169.315979 z"/>
          </g>
        </g>
      </g>
    </svg>
  );
}

export default function SocialTab({ fetchWithAuth }) {
  const [stats, setStats] = useState(null);
  const [posts, setPosts] = useState([]);
  const [previews, setPreviews] = useState({});
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [showCompose, setShowCompose] = useState(false);
  const [publishingLive, setPublishingLive] = useState(() => localStorage.getItem('social_live') === 'true');
  const [scheduleModal, setScheduleModal] = useState(null); // post id or null
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleTime, setScheduleTime] = useState('09:00');

  const toggleLive = () => {
    const next = !publishingLive;
    if (next && !window.confirm('Enable live publishing? Posts will be sent to Twitter/Instagram/Threads when you click Publish.')) return;
    setPublishingLive(next);
    localStorage.setItem('social_live', String(next));
  };

  // Filters
  const [platform, setPlatform] = useState('all');
  const [status, setStatus] = useState('all');
  const [postType, setPostType] = useState('all');

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/social/stats`);
      if (res.ok) setStats(await res.json());
    } catch (err) {
      console.error('Failed to fetch social stats:', err);
    }
  }, [fetchWithAuth]);

  const fetchPosts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: '50' });
      if (platform !== 'all') params.set('platform', platform);
      if (status !== 'all') params.set('status', status);
      if (postType !== 'all') params.set('post_type', postType);

      const res = await fetchWithAuth(`${API_URL}/api/admin/social/posts?${params}`);
      if (res.ok) {
        const data = await res.json();
        setPosts(data.posts || []);
      }
    } catch (err) {
      console.error('Failed to fetch social posts:', err);
    } finally {
      setLoading(false);
    }
  }, [fetchWithAuth, platform, status, postType]);

  const fetchPreview = useCallback(async (postId) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/social/posts/${postId}/preview`);
      if (res.ok) {
        const data = await res.json();
        setPreviews(prev => ({ ...prev, [postId]: data }));
      }
    } catch (err) {
      console.error(`Failed to fetch preview for post ${postId}:`, err);
    }
  }, [fetchWithAuth]);

  useEffect(() => {
    fetchStats();
    fetchPosts();
  }, [fetchStats, fetchPosts]);

  // Fetch previews for posts that have images
  useEffect(() => {
    posts.forEach(post => {
      if (post.image_s3_key && !previews[post.id]) {
        fetchPreview(post.id);
      }
    });
  }, [posts, previews, fetchPreview]);

  const handleAction = async (postId, action, method = 'POST', confirmMsg = null, successMsg = null) => {
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    setActionLoading(prev => ({ ...prev, [postId]: action }));
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/social/${action}`, { method });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`Action failed: ${err.detail || res.statusText}`);
      } else if (successMsg) {
        alert(successMsg);
      }
      await Promise.all([fetchStats(), fetchPosts()]);
    } catch (err) {
      console.error(`Action ${action} failed:`, err);
      alert(`Action failed: ${err.message}`);
    } finally {
      setActionLoading(prev => ({ ...prev, [postId]: null }));
    }
  };

  const approve = (id) => handleAction(id, `posts/${id}/approve`, 'POST', null, 'Post approved! Switch to "Approved" filter to see it.');
  const reject = (id) => handleAction(id, `posts/${id}/reject`, 'POST', null, 'Post rejected.');
  const regenerate = (id) => handleAction(id, `posts/${id}/regenerate`);
  const deletePost = (id) => handleAction(id, `posts/${id}`, 'DELETE', 'Delete this post? This cannot be undone.');

  const publish = async (id) => {
    if (!window.confirm('Publish this post live? This will post to the platform immediately.')) return;
    setActionLoading(prev => ({ ...prev, [id]: 'publish' }));
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/social/posts/${id}/publish`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        const url = data.tweet_url || data.permalink || '';
        alert(`Published successfully!${url ? `\n${url}` : ''}`);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Publish failed: ${err.detail || res.statusText}`);
      }
      await Promise.all([fetchStats(), fetchPosts()]);
    } catch (err) {
      console.error('Publish failed:', err);
      alert(`Publish failed: ${err.message}`);
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: null }));
    }
  };

  const editPost = async (id, textContent, hashtags) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/social/posts/${id}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text_content: textContent, hashtags }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`Edit failed: ${err.detail || res.statusText}`);
        return false;
      }
      await fetchPosts();
      return true;
    } catch (err) {
      console.error('Edit failed:', err);
      alert(`Edit failed: ${err.message}`);
      return false;
    }
  };

  const schedulePost = (id) => {
    // Open the schedule modal with a default date of tomorrow
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setScheduleDate(tomorrow.toISOString().slice(0, 10));
    setScheduleTime('09:00');
    setScheduleModal(id);
  };

  const confirmSchedule = async () => {
    if (!scheduleDate || !scheduleTime || !scheduleModal) return;
    const id = scheduleModal;
    // Convert EST date+time to UTC ISO string
    const estDatetime = `${scheduleDate}T${scheduleTime}:00`;
    const utcDate = new Date(new Date(estDatetime + '-05:00').toISOString());
    const isoStr = utcDate.toISOString();

    setScheduleModal(null);
    setActionLoading(prev => ({ ...prev, [id]: 'schedule' }));
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/social/posts/${id}/schedule`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ publish_at: isoStr }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`Schedule failed: ${err.detail || res.statusText}`);
      }
      await Promise.all([fetchStats(), fetchPosts()]);
    } catch (err) {
      console.error('Schedule failed:', err);
      alert(`Schedule failed: ${err.message}`);
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: null }));
    }
  };

  const cancelPost = async (id) => {
    if (!window.confirm('Cancel this scheduled post?')) return;
    setActionLoading(prev => ({ ...prev, [id]: 'cancel' }));
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/social/posts/${id}/cancel`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`Cancel failed: ${err.detail || res.statusText}`);
      }
      await Promise.all([fetchStats(), fetchPosts()]);
    } catch (err) {
      console.error('Cancel failed:', err);
      alert(`Cancel failed: ${err.message}`);
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: null }));
    }
  };

  const generateChart = async (id) => {
    setActionLoading(prev => ({ ...prev, [id]: 'generate-chart' }));
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/social/generate-chart/${id}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setPreviews(prev => ({ ...prev, [id]: { ...prev[id], image_url: data.image_url } }));
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Chart generation failed: ${err.detail || res.statusText}`);
      }
      await Promise.all([fetchStats(), fetchPosts()]);
    } catch (err) {
      console.error('Chart generation failed:', err);
      alert(`Chart generation failed: ${err.message}`);
    } finally {
      setActionLoading(prev => ({ ...prev, [id]: null }));
    }
  };

  const handleCompose = async (composeData) => {
    try {
      const res = await fetchWithAuth(`${API_URL}/api/admin/social/posts/compose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(composeData),
      });
      if (res.ok) {
        setShowCompose(false);
        await Promise.all([fetchStats(), fetchPosts()]);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(`Compose failed: ${err.detail || res.statusText}`);
      }
    } catch (err) {
      console.error('Compose failed:', err);
      alert(`Compose failed: ${err.message}`);
    }
  };

  const twitterPosts = posts.filter(p => p.platform === 'twitter');
  const instagramPosts = posts.filter(p => p.platform === 'instagram');
  const threadsPosts = posts.filter(p => p.platform === 'threads');

  return (
    <div className="space-y-6">
      {/* Live Switch */}
      <div className={`flex items-center justify-between rounded-xl border-2 px-5 py-3 transition-colors ${
        publishingLive
          ? 'bg-green-50 border-green-300'
          : 'bg-amber-50 border-amber-300'
      }`}>
        <div className="flex items-center gap-3">
          <Power size={18} className={publishingLive ? 'text-green-600' : 'text-amber-600'} />
          <div>
            <span className={`text-sm font-semibold ${publishingLive ? 'text-green-800' : 'text-amber-800'}`}>
              {publishingLive ? 'Publishing is LIVE' : 'Publishing is OFF'}
            </span>
            <p className="text-xs text-gray-500">
              {publishingLive
                ? 'Publish buttons are active — posts will go live to Twitter/Instagram/Threads.'
                : 'Publish buttons are hidden. Enable when ready to go live.'}
            </p>
          </div>
        </div>
        <button
          onClick={toggleLive}
          className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${
            publishingLive ? 'bg-green-500' : 'bg-gray-300'
          }`}
        >
          <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
            publishingLive ? 'translate-x-6' : 'translate-x-1'
          }`} />
        </button>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Share2 className="text-blue-600" />}
          label="Total Posts"
          value={stats?.total ?? '-'}
        />
        <StatCard
          icon={<MessageSquare className="text-gray-600" />}
          label="Drafts"
          value={stats?.by_status?.draft ?? '-'}
          subtext="Pending review"
        />
        <StatCard
          icon={<Check className="text-green-600" />}
          label="Approved"
          value={stats?.by_status?.approved ?? '-'}
        />
        <StatCard
          icon={<Globe className="text-purple-600" />}
          label="Posted"
          value={stats?.by_status?.posted ?? '-'}
        />
      </div>

      {/* Filters Row + Compose Button */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <div className="flex flex-wrap items-end gap-6">
          <FilterGroup label="Platform" options={PLATFORMS} value={platform} onChange={setPlatform} />
          <FilterGroup label="Status" options={STATUSES} value={status} onChange={setStatus} />
          <FilterGroup label="Post Type" options={POST_TYPES} value={postType} onChange={setPostType} />
          <div className="ml-auto">
            <button
              onClick={() => setShowCompose(true)}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
            >
              <Plus size={16} />
              New Post
            </button>
          </div>
        </div>
      </div>

      {/* Compose Modal */}
      {showCompose && (
        <ComposeModal onClose={() => setShowCompose(false)} onSubmit={handleCompose} />
      )}

      {/* Schedule Modal */}
      {scheduleModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setScheduleModal(null)}>
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <Calendar size={18} className="text-amber-500" />
              Schedule Post
            </h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Date</label>
                <input
                  type="date"
                  value={scheduleDate}
                  onChange={e => setScheduleDate(e.target.value)}
                  min={new Date().toISOString().slice(0, 10)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">Time (EST)</label>
                <select
                  value={scheduleTime}
                  onChange={e => setScheduleTime(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                >
                  {['06:00','07:00','08:00','09:00','09:30','10:00','10:30','11:00','11:30','12:00','12:30','13:00','14:00','15:00','16:00','17:00','18:00','19:00','20:00','21:00'].map(t => (
                    <option key={t} value={t}>
                      {new Date(`2026-01-01T${t}`).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })} ET
                    </option>
                  ))}
                </select>
              </div>
              <p className="text-xs text-gray-400">
                Will publish: {scheduleDate && scheduleTime ? `${new Date(scheduleDate + 'T' + scheduleTime + ':00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })} at ${new Date(`2026-01-01T${scheduleTime}`).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })} ET` : '—'}
              </p>
            </div>
            <div className="flex gap-2 mt-5">
              <button
                onClick={() => setScheduleModal(null)}
                className="flex-1 px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmSchedule}
                disabled={!scheduleDate || !scheduleTime}
                className="flex-1 px-4 py-2 text-sm font-medium text-white bg-amber-500 hover:bg-amber-600 rounded-lg transition-colors disabled:opacity-50"
              >
                <span className="flex items-center justify-center gap-1.5">
                  <Calendar size={14} />
                  Schedule
                </span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Launch Queue — show above feed, hide once launch posts have been queued */}
      {!posts.some(p => p.post_type === 'manual') && (
        <LaunchQueueSection fetchWithAuth={fetchWithAuth} onQueued={() => Promise.all([fetchStats(), fetchPosts()])} posts={posts} />
      )}

      {/* Post Feed */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600"></div>
        </div>
      ) : posts.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <Share2 size={48} className="mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-semibold text-gray-700 mb-2">No social posts yet</h3>
          <p className="text-gray-500 mb-4">Posts are auto-generated nightly at 8 PM ET from walk-forward simulation results.</p>
          <button
            onClick={() => setShowCompose(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
          >
            <Plus size={16} />
            Create Your First Post
          </button>
        </div>
      ) : platform === 'all' ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Twitter/X ({twitterPosts.length})</h3>
            {twitterPosts.length === 0 ? (
              <p className="text-sm text-gray-400 py-4">No Twitter posts match filters.</p>
            ) : (
              twitterPosts.map(post => (
                <TwitterCard
                  key={post.id}
                  post={post}
                  preview={previews[post.id]}
                  actionLoading={actionLoading[post.id]}
                  onApprove={approve}
                  onReject={reject}
                  onRegenerate={regenerate}
                  onDelete={deletePost}
                  onPublish={publish}
                  onEdit={editPost}
                  onSchedule={schedulePost}
                  onCancel={cancelPost}
                  publishingLive={publishingLive}
                />
              ))
            )}
          </div>
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Instagram ({instagramPosts.length})</h3>
            {instagramPosts.length === 0 ? (
              <p className="text-sm text-gray-400 py-4">No Instagram posts match filters.</p>
            ) : (
              instagramPosts.map(post => (
                <InstagramCard
                  key={post.id}
                  post={post}
                  preview={previews[post.id]}
                  actionLoading={actionLoading[post.id]}
                  onApprove={approve}
                  onReject={reject}
                  onRegenerate={regenerate}
                  onDelete={deletePost}
                  onPublish={publish}
                  onEdit={editPost}
                  onGenerateChart={generateChart}
                  onSchedule={schedulePost}
                  onCancel={cancelPost}
                  publishingLive={publishingLive}
                />
              ))
            )}
          </div>
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Threads ({threadsPosts.length})</h3>
            {threadsPosts.length === 0 ? (
              <p className="text-sm text-gray-400 py-4">No Threads posts match filters.</p>
            ) : (
              threadsPosts.map(post => (
                <ThreadsCard
                  key={post.id}
                  post={post}
                  actionLoading={actionLoading[post.id]}
                  onApprove={approve}
                  onReject={reject}
                  onRegenerate={regenerate}
                  onDelete={deletePost}
                  onPublish={publish}
                  onEdit={editPost}
                  onSchedule={schedulePost}
                  onCancel={cancelPost}
                  publishingLive={publishingLive}
                />
              ))
            )}
          </div>
        </div>
      ) : platform === 'twitter' ? (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Twitter/X ({twitterPosts.length})</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {twitterPosts.map(post => (
              <TwitterCard
                key={post.id}
                post={post}
                preview={previews[post.id]}
                actionLoading={actionLoading[post.id]}
                onApprove={approve}
                onReject={reject}
                onRegenerate={regenerate}
                onDelete={deletePost}
                onPublish={publish}
                onEdit={editPost}
                onSchedule={schedulePost}
                onCancel={cancelPost}
                publishingLive={publishingLive}
              />
            ))}
          </div>
        </div>
      ) : platform === 'threads' ? (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Threads ({threadsPosts.length})</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {threadsPosts.map(post => (
              <ThreadsCard
                key={post.id}
                post={post}
                actionLoading={actionLoading[post.id]}
                onApprove={approve}
                onReject={reject}
                onRegenerate={regenerate}
                onDelete={deletePost}
                onPublish={publish}
                onEdit={editPost}
                onSchedule={schedulePost}
                onCancel={cancelPost}
                publishingLive={publishingLive}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Instagram ({instagramPosts.length})</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {instagramPosts.map(post => (
              <InstagramCard
                key={post.id}
                post={post}
                preview={previews[post.id]}
                actionLoading={actionLoading[post.id]}
                onApprove={approve}
                onReject={reject}
                onRegenerate={regenerate}
                onDelete={deletePost}
                onPublish={publish}
                onEdit={editPost}
                onSchedule={schedulePost}
                onCancel={cancelPost}
                onGenerateChart={generateChart}
                publishingLive={publishingLive}
              />
            ))}
          </div>
        </div>
      )}

    </div>
  );
}

const LAUNCH_POSTS = [
  {
    id: 'launch-1',
    label: 'Launch Announcement',
    imageUrl: '/launch-cards/launch-1.png',
    twitter: {
      text: "We built a trading system. Tested it across 5 years of real data without peeking at the answers. +289%.\n\n~15 buy signals per month. No hindsight. No hand-waving. Just math.\n\nRigaCap is live. rigacap.com",
      hashtags: '#trading #algotrading #stockmarket',
    },
    instagram: {
      text: "We built a trading system.\n\nThen we did something most people skip \u2014 we tested it honestly. Year by year, no hindsight bias, across bull markets, bear markets, and everything in between.\n\n+289% over 5 years. 31% annualized. 80% of years profitable.\n\nBut here's the part that actually matters: it generates ~15 buy signals per month. 6\u20138 high-conviction picks every two weeks, delivered before the market opens.\n\nWe didn't backtest it and call it a day. We walk-forward tested it \u2014 the system never saw future data. It had to figure it out in real time, just like you do.\n\nNo hand-waving. No vibes. Just math.\n\nRigaCap is live.",
      hashtags: '#trading #algotrading #stockmarket #investing #rigacap',
    },
    threads: {
      text: "We built a trading system. Tested it across 5 years of real market data without peeking at the answers.\n\n+289%. 31% annualized. 80% of years profitable.\n\n~15 buy signals per month. No hindsight. No hand-waving. Just math.\n\nRigaCap is live.\n\nrigacap.com",
    },
  },
  {
    id: 'launch-2',
    label: 'Performance Stats',
    imageUrl: '/launch-cards/launch-2.png',
    twitter: {
      text: "Our 5-year walk-forward report card:\n\n2021-22: +62.0% \u2705\n2022-23: -13.2% \u274c (bear market, it happens)\n2023-24: +22.2% \u2705\n2024-25: +20.7% \u2705\n2025-26: +87.5% \u2705\n\nTotal: +289% | 718 trades | ~15 signals/month\n\nWe show the bad year too. That's how trust works.",
      hashtags: '#trading #performance #walkforward',
    },
    instagram: {
      text: "Let's talk numbers. All of them.\n\n2021-2022: +62.0% (Sharpe 1.21)\n2022-2023: -13.2% (yes, we lost money in the bear market)\n2023-2024: +22.2% (Sharpe 1.02)\n2024-2025: +20.7% (Sharpe 0.89)\n2025-2026: +87.5% (Sharpe 2.32)\n\n5-Year Total: +289% | 31% annualized\n718 total trades | ~15 signals per month\nMax drawdown: -15.1%\n\nWe show the losing year because hiding it would make us like everyone else. Every period tested independently \u2014 no curve-fitting, no cherry-picking, no \"if you'd just bought here\" nonsense.\n\nAnd when the market went sideways in 2022? Zero signals for 5 months. The system said \"nah\" and sat on its hands. That's not a bug. That's risk management.\n\nPast performance doesn't guarantee future results. But honest testing beats a screenshot of someone's best week.",
      hashtags: '#trading #algotrading #performance #walkforward #stockmarket #investing #rigacap',
    },
    threads: {
      text: "Our 5-year walk-forward report card:\n\n2021-22: +62.0%\n2022-23: -13.2% (bear market, it happens)\n2023-24: +22.2%\n2024-25: +20.7%\n2025-26: +87.5%\n\nTotal: +289% | 718 trades | ~15 signals/month\n\nWe show the bad year too. That's how trust works.\n\nrigacap.com/track-record",
    },
  },
  {
    id: 'launch-3',
    label: 'How It Works',
    imageUrl: '/launch-cards/launch-3.png',
    twitter: {
      text: "How we pick trades:\n\n1\uFE0F\u20E3 Timing \u2014 proprietary breakout detection catches moves before the crowd\n2\uFE0F\u20E3 Quality \u2014 only top-ranked momentum stocks pass\n3\uFE0F\u20E3 Risk \u2014 7 market regimes, adapted daily\n\nAll 3 must agree. Most stocks fail. That's the point.\n\n~6\u20138 make the cut every 2 weeks.",
      hashtags: '#trading #ensemble #momentum #riskmanagement',
    },
    instagram: {
      text: "Why three factors instead of one? Because markets are complicated and anyone who says otherwise is selling you something.\n\nFactor 1: Breakout Timing\nOur proprietary accumulation breakout model catches moves early \u2014 before they show up on everyone's screener.\n\nFactor 2: Momentum Quality\nNot all breakouts deserve your money. We rank by 10-day and 60-day momentum, filter for volatility, and confirm with volume.\n\nFactor 3: Regime Detection\n7 market regimes detected daily. Because \"buy the dip\" is great advice in a bull market and terrible advice in a crash.\n\nAll 3 factors must align for a signal. Out of thousands of stocks, only 6\u20138 make the cut every two weeks. Most days, nothing qualifies.\n\nThat's not a bug \u2014 it's the whole point. Picky systems make money. Trigger-happy ones don't.",
      hashtags: '#trading #algotrading #ensemble #momentum #riskmanagement #rigacap',
    },
    threads: {
      text: "How we pick trades:\n\n1. Timing \u2014 proprietary breakout detection catches moves before the crowd\n2. Quality \u2014 only top-ranked momentum stocks pass\n3. Risk \u2014 7 market regimes, adapted daily\n\nAll 3 must agree. Most stocks fail. That's the point.\n\nOut of thousands scanned, ~6\u20138 make the cut every 2 weeks.\n\nrigacap.com",
    },
  },
  {
    id: 'launch-4',
    label: '7 Market Regimes',
    imageUrl: '/launch-cards/launch-4.png',
    twitter: {
      text: "Your strategy probably has one mode.\n\nOurs has 7:\n\nStrong Bull \u2192 full send\nWeak Bull \u2192 be picky\nRotating Bull \u2192 follow the leaders\nRange Bound \u2192 sit on hands\nWeak Bear \u2192 tighten up\nPanic/Crash \u2192 go home\nRecovery \u2192 start nibbling\n\nIn 2022 it said \"go home\" for 5 months. No signals. No losses.\n\nThe market adapts. Your strategy should too.",
      hashtags: '#trading #marketregime #riskmanagement',
    },
    instagram: {
      text: "\"Just buy the dip.\"\n\nOk, but which dip? The one that bounces 15%, or the one that keeps dipping for 6 months?\n\nThat's why we built a 7-regime detection system:\n\nStrong Bull \u2014 Broad rally. Full exposure. Let it ride.\nWeak Bull \u2014 Narrow leadership. Cherry-pick the best.\nRotating Bull \u2014 Sectors taking turns. Follow the momentum.\nRange Bound \u2014 Choppy. Reduce size, wait for clarity.\nWeak Bear \u2014 Slow bleed. Tighten stops, protect capital.\nPanic/Crash \u2014 Exit everything. Ego is expensive.\nRecovery \u2014 The brave (and the algorithmic) start buying.\n\nFun fact: in the 2022 bear market, the system went quiet for 5 consecutive months. Zero signals. It literally refused to trade. That saved our walk-forward from what would've been a brutal drawdown.\n\nNo vibes. No gut feelings. Just math, updated daily.",
      hashtags: '#trading #algotrading #marketregime #riskmanagement #investing #rigacap',
    },
    threads: {
      text: "Your strategy probably has one mode. Ours has 7.\n\nStrong Bull \u2192 full send\nWeak Bull \u2192 be picky\nRotating Bull \u2192 follow the leaders\nRange Bound \u2192 sit on hands\nWeak Bear \u2192 tighten up\nPanic/Crash \u2192 go home\nRecovery \u2192 start nibbling\n\nIn 2022 it said \"go home\" for 5 months. No signals. No losses.\n\nThe market adapts. Your strategy should too.\n\nrigacap.com",
    },
  },
  {
    id: 'launch-5',
    label: 'Signal Teaser',
    imageUrl: '/launch-cards/launch-5.png',
    twitter: {
      text: "Every two weeks we scan thousands of stocks through a 3-factor gauntlet.\n\nMost fail. 6\u20138 survive.\n\nThose land in your inbox before the market opens. ~15 signals per month when conditions are right. Zero when they're not.\n\nrigacap.com",
      hashtags: '#trading #signals #stockmarket',
    },
    instagram: {
      text: "Here's what happens every two weeks inside RigaCap:\n\nScan thousands of stocks. Rank by momentum. Filter for quality. Check the market regime. Score them. Rank again. Throw out anything that doesn't pass all 3 factors.\n\nThe result? 6\u20138 high-conviction buy signals, delivered to your inbox before the market opens.\n\nThat's ~15 signals per month when conditions are healthy. And when the market is ugly? The system goes quiet. No forced trades. No \"well, this one looks okay I guess.\" Just silence \u2014 which is exactly what you want when everyone else is panicking.\n\nNo screeners to configure. No charts to stare at. No FOMO-scrolling at 2am.\n\nJust signals. Walk-forward verified. Every single one.\n\nrigacap.com",
      hashtags: '#trading #signals #stockmarket #algotrading #investing #rigacap',
    },
    threads: {
      text: "Every two weeks we scan thousands of stocks through a 3-factor gauntlet.\n\nMost fail. 6\u20138 survive.\n\nThose land in your inbox before the market opens. ~15 signals per month when conditions are right. Zero when they're not.\n\nNo screeners. No charts. No 2am FOMO-scrolling.\n\nJust signals. Walk-forward verified.\n\nrigacap.com",
    },
  },
];

function LaunchQueueSection({ fetchWithAuth, onQueued, posts = [] }) {
  const [expanded, setExpanded] = useState(false);
  const [queueing, setQueueing] = useState(false);

  // Check which platforms already have launch posts queued
  const existingPlatforms = new Set();
  for (const lp of LAUNCH_POSTS) {
    for (const plat of ['twitter', 'instagram', 'threads']) {
      const prefix = lp[plat]?.text?.substring(0, 30);
      if (prefix && posts.some(p => p.platform === plat && p.text_content?.startsWith(prefix))) {
        existingPlatforms.add(plat);
      }
    }
  }
  const missingPlatforms = ['twitter', 'instagram', 'threads'].filter(p => !existingPlatforms.has(p));
  const alreadyQueued = missingPlatforms.length === 0;
  const [queued, setQueued] = useState(false);

  const noop = () => {};

  const queueAllPosts = async () => {
    const platformsToQueue = missingPlatforms.length > 0 ? missingPlatforms : ['twitter', 'instagram', 'threads'];
    const count = platformsToQueue.length * LAUNCH_POSTS.length;
    if (!window.confirm(`Queue ${count} launch posts (${platformsToQueue.join(' + ')}) as drafts?`)) return;
    setQueueing(true);
    let success = 0;
    for (const lp of LAUNCH_POSTS) {
      for (const platform of platformsToQueue) {
        const content = lp[platform];
        if (!content) continue;
        try {
          const res = await fetchWithAuth(`${API_URL}/api/admin/social/posts/compose`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              platform,
              text_content: content.text,
              hashtags: content.hashtags || '',
              post_type: 'manual',
              status: 'draft',
              image_s3_key: platform !== 'threads' && lp.imageUrl ? `social/images/${lp.imageUrl.split('/').pop()}` : undefined,
            }),
          });
          if (res.ok) success++;
        } catch (err) {
          console.error(`Failed to queue ${lp.label} (${platform}):`, err);
        }
      }
    }
    setQueueing(false);
    setQueued(true);
    alert(`Queued ${success} of ${count} launch posts as drafts.`);
    if (onQueued) onQueued();
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Rocket size={18} className="text-amber-500" />
          <span className="text-sm font-semibold text-gray-800">Launch Posts Preview</span>
          <span className="text-xs text-gray-400">5 concepts &times; 3 platforms = 15 posts</span>
        </div>
        {expanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
      </button>

      {expanded && (
        <div className="border-t border-gray-200 p-6 space-y-8">
          {/* Queue button */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">Preview how launch posts will look. When ready, queue them all as drafts to review and approve individually.</p>
            <button
              onClick={queueAllPosts}
              disabled={queueing || queued || alreadyQueued}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                queued || alreadyQueued
                  ? 'bg-green-100 text-green-700 cursor-default'
                  : 'bg-amber-500 hover:bg-amber-600 text-white disabled:opacity-50'
              }`}
            >
              {queueing ? (
                <><RefreshCw size={14} className="animate-spin" /> Queueing...</>
              ) : queued || alreadyQueued ? (
                <><Check size={14} /> All Queued</>
              ) : missingPlatforms.length < 3 ? (
                <><Plus size={14} /> Queue {missingPlatforms.join(' + ')} Drafts</>
              ) : (
                <><Plus size={14} /> Queue All as Drafts</>
              )}
            </button>
          </div>

          {LAUNCH_POSTS.map((lp, idx) => {
            const twitterPost = {
              id: lp.id + '-tw',
              post_type: 'manual',
              platform: 'twitter',
              status: 'draft',
              text_content: lp.twitter.text,
              hashtags: lp.twitter.hashtags,
              created_at: new Date().toISOString(),
            };
            const instagramPost = {
              id: lp.id + '-ig',
              post_type: 'manual',
              platform: 'instagram',
              status: 'draft',
              text_content: lp.instagram.text,
              hashtags: lp.instagram.hashtags,
              created_at: new Date().toISOString(),
            };
            const threadsPost = {
              id: lp.id + '-th',
              post_type: 'manual',
              platform: 'threads',
              status: 'draft',
              text_content: lp.threads.text,
              hashtags: '',
              created_at: new Date().toISOString(),
            };

            return (
              <div key={lp.id}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-amber-100 text-amber-700 text-xs font-bold">{idx + 1}</span>
                  <h4 className="text-sm font-semibold text-gray-700">{lp.label}</h4>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <TwitterCard
                    post={twitterPost}
                    preview={null}
                    actionLoading={null}
                    onApprove={noop}
                    onReject={noop}
                    onRegenerate={noop}
                    onDelete={noop}
                    onPublish={noop}
                    onEdit={noop}
                    publishingLive={false}
                  />
                  <InstagramCard
                    post={instagramPost}
                    preview={lp.imageUrl ? { image_url: lp.imageUrl } : null}
                    actionLoading={null}
                    onApprove={noop}
                    onReject={noop}
                    onRegenerate={noop}
                    onDelete={noop}
                    onPublish={noop}
                    onEdit={noop}
                    onGenerateChart={noop}
                    publishingLive={false}
                  />
                  <ThreadsCard
                    post={threadsPost}
                    actionLoading={null}
                    onApprove={noop}
                    onReject={noop}
                    onRegenerate={noop}
                    onDelete={noop}
                    onPublish={noop}
                    onEdit={noop}
                    publishingLive={false}
                  />
                </div>
                {idx < LAUNCH_POSTS.length - 1 && <hr className="mt-6 border-gray-100" />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ComposeModal({ onClose, onSubmit }) {
  const [composePlatform, setComposePlatform] = useState('twitter');
  const [text, setText] = useState('');
  const [hashtags, setHashtags] = useState('');
  const [saving, setSaving] = useState(false);

  const fullText = hashtags ? `${text}\n\n${hashtags}` : text;
  const charCount = fullText.length;
  const charMax = composePlatform === 'twitter' ? 280 : composePlatform === 'threads' ? 500 : null;
  const overLimit = charMax && charCount > charMax;

  const handleSubmit = async (saveStatus) => {
    if (!text.trim()) return;
    setSaving(true);
    await onSubmit({
      platform: composePlatform,
      text_content: text,
      hashtags: hashtags || null,
      post_type: 'manual',
      status: saveStatus,
    });
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-900">New Post</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
          </div>
        </div>

        <div className="p-6 space-y-5">
          {/* Platform Toggle */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Platform</label>
            <div className="flex gap-2">
              {['twitter', 'instagram', 'threads'].map(p => (
                <button
                  key={p}
                  onClick={() => setComposePlatform(p)}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                    composePlatform === p
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {p === 'twitter' ? 'Twitter/X' : p === 'threads' ? 'Threads' : 'Instagram'}
                </button>
              ))}
            </div>
          </div>

          {/* Text Area */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Post Text</label>
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              rows={5}
              className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              placeholder={composePlatform === 'twitter' ? "What's happening?" : "Write a caption..."}
            />
          </div>

          {/* Hashtags */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Hashtags</label>
            <input
              type="text"
              value={hashtags}
              onChange={e => setHashtags(e.target.value)}
              className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="#trading #momentum #stocks"
            />
          </div>

          {/* Preview */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Preview</label>
            {(composePlatform === 'twitter' || composePlatform === 'threads') ? (
              <div className="border border-gray-200 rounded-xl p-4">
                <div className="flex gap-3">
                  <RigaCapLogo size={40} className="shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1">
                      <span className="font-bold text-sm text-gray-900">RigaCap</span>
                      <span className="text-sm text-gray-500">@rigacap</span>
                    </div>
                    <p className="text-sm text-gray-900 mt-1 whitespace-pre-wrap break-words">{text || 'Your post text here...'}</p>
                    {hashtags && <p className="text-sm text-blue-500 mt-1 break-words">{hashtags}</p>}
                  </div>
                </div>
              </div>
            ) : (
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                <div className="flex items-center gap-2.5 px-3 py-2.5 border-b border-gray-100">
                  <RigaCapLogo size={32} className="shrink-0" />
                  <span className="font-semibold text-sm text-gray-900">rigacap</span>
                </div>
                <div className="w-full aspect-[4/5] bg-gray-50 flex items-center justify-center">
                  <Image size={40} className="text-gray-300" />
                </div>
                <div className="px-3 py-2.5">
                  <p className="text-sm text-gray-900">
                    <span className="font-semibold">rigacap</span>{' '}
                    <span className="whitespace-pre-wrap break-words">{text || 'Your caption here...'}</span>
                  </p>
                  {hashtags && <p className="text-sm text-blue-500 mt-1 break-words">{hashtags}</p>}
                </div>
              </div>
            )}
          </div>

          {/* Char count for Twitter/Threads */}
          {charMax && (
            <div className={`text-xs font-medium ${overLimit ? 'text-red-600' : 'text-gray-400'}`}>
              {charCount}/{charMax}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={() => handleSubmit('draft')}
            disabled={!text.trim() || saving}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50"
          >
            Save as Draft
          </button>
          <button
            onClick={() => handleSubmit('approved')}
            disabled={!text.trim() || saving || overLimit}
            className="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
          >
            Save & Approve
          </button>
        </div>
      </div>
    </div>
  );
}

function FilterGroup({ label, options, value, onChange }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1.5">{label}</label>
      <div className="flex gap-1">
        {options.map(opt => (
          <button
            key={opt.id}
            onClick={() => onChange(opt.id)}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              value === opt.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, subtext }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <span className="text-sm font-medium text-gray-500">{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      {subtext && <p className="text-sm text-gray-500 mt-1">{subtext}</p>}
    </div>
  );
}

function PostBadges({ post }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[post.post_type] || 'bg-gray-100 text-gray-600'}`}>
        {TYPE_LABELS[post.post_type] || post.post_type}
      </span>
      <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${STATUS_COLORS[post.status] || 'bg-gray-100 text-gray-600'}`}>
        {post.status}
      </span>
      {post.ai_generated && (
        <span className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
          <Sparkles size={10} />
          AI
        </span>
      )}
      {post.scheduled_for && (
        <span className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-700" title={`Scheduled for ${new Date(post.scheduled_for + 'Z').toLocaleString()}`}>
          <Calendar size={11} />
          {new Date(post.scheduled_for + 'Z').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })} @ {new Date(post.scheduled_for + 'Z').toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
        </span>
      )}
      <span className="text-xs text-gray-400">
        {new Date(post.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
      </span>
    </div>
  );
}

function ActionButtons({ post, actionLoading, onApprove, onReject, onRegenerate, onDelete, onPublish, onSchedule, onCancel, publishingLive, extraButtons }) {
  const isLoading = !!actionLoading;
  const canModify = post.status === 'draft' || post.status === 'rejected' || post.status === 'scheduled';

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {post.status === 'approved' && publishingLive && (
        <button
          onClick={() => onPublish(post.id)}
          disabled={isLoading}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
          title="Publish to platform"
        >
          {actionLoading === 'publish' ? <RefreshCw size={13} className="animate-spin" /> : <Send size={13} />}
          Publish
        </button>
      )}
      {post.status === 'approved' && !post.scheduled_for && onSchedule && (
        <button
          onClick={() => onSchedule(post.id)}
          disabled={isLoading}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg transition-colors disabled:opacity-50"
          title="Schedule for later"
        >
          <Calendar size={13} />
          Schedule
        </button>
      )}
      {(post.status === 'approved' || post.status === 'draft') && post.scheduled_for && onCancel && (
        <button
          onClick={() => onCancel(post.id)}
          disabled={isLoading}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-red-700 bg-red-50 hover:bg-red-100 rounded-lg transition-colors disabled:opacity-50"
          title="Cancel scheduled post"
        >
          <Ban size={13} />
          Cancel
        </button>
      )}
      {canModify && (
        <button
          onClick={() => onApprove(post.id)}
          disabled={isLoading}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-green-700 bg-green-50 hover:bg-green-100 rounded-lg transition-colors disabled:opacity-50"
          title="Approve"
        >
          {actionLoading === 'approve' ? <RefreshCw size={13} className="animate-spin" /> : <Check size={13} />}
          Approve
        </button>
      )}
      {(post.status === 'draft' || post.status === 'approved') && (
        <button
          onClick={() => onReject(post.id)}
          disabled={isLoading}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-red-700 bg-red-50 hover:bg-red-100 rounded-lg transition-colors disabled:opacity-50"
          title="Reject"
        >
          {actionLoading === 'reject' ? <RefreshCw size={13} className="animate-spin" /> : <X size={13} />}
          Reject
        </button>
      )}
      {extraButtons}
      {post.status !== 'posted' && post.status !== 'cancelled' && (
        <button
          onClick={() => onRegenerate(post.id)}
          disabled={isLoading}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
          title="Regenerate"
        >
          {actionLoading === 'regenerate' ? <RefreshCw size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          Regen
        </button>
      )}
      {(post.status === 'draft' || post.status === 'rejected') && (
        <button
          onClick={() => onDelete(post.id)}
          disabled={isLoading}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
          title="Delete"
        >
          {actionLoading === 'delete' ? <RefreshCw size={13} className="animate-spin" /> : <Trash2 size={13} />}
        </button>
      )}
    </div>
  );
}

function splitTextAndHashtags(text, hashtags) {
  const mainText = text || '';
  const tags = hashtags || '';
  return { mainText, tags };
}

function InlineEditableText({ text, hashtags, postId, canEdit, onEdit }) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(text);
  const [editHashtags, setEditHashtags] = useState(hashtags);
  const [saving, setSaving] = useState(false);

  if (!editing) {
    return (
      <div
        className={`group relative ${canEdit ? 'cursor-pointer' : ''}`}
        onClick={() => { if (canEdit) { setEditText(text); setEditHashtags(hashtags); setEditing(true); } }}
      >
        <p className="text-sm text-gray-900 whitespace-pre-wrap break-words">{text}</p>
        {hashtags && <p className="text-sm text-blue-500 mt-1 break-words">{hashtags}</p>}
        {canEdit && (
          <div className="absolute top-0 right-0 opacity-0 group-hover:opacity-100 transition-opacity">
            <Edit3 size={12} className="text-gray-400" />
          </div>
        )}
      </div>
    );
  }

  const handleSave = async () => {
    setSaving(true);
    const ok = await onEdit(postId, editText, editHashtags);
    setSaving(false);
    if (ok) setEditing(false);
  };

  return (
    <div className="space-y-2">
      <textarea
        value={editText}
        onChange={e => setEditText(e.target.value)}
        rows={3}
        className="w-full border border-blue-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
        autoFocus
      />
      <input
        type="text"
        value={editHashtags}
        onChange={e => setEditHashtags(e.target.value)}
        className="w-full border border-blue-300 rounded-lg p-2 text-sm text-blue-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        placeholder="Hashtags"
      />
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50"
        >
          <Save size={12} /> Save
        </button>
        <button
          onClick={() => setEditing(false)}
          className="px-2.5 py-1 text-xs font-medium text-gray-600 hover:text-gray-800"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function TwitterCard({ post, preview, actionLoading, onApprove, onReject, onRegenerate, onDelete, onPublish, onEdit, onSchedule, onCancel, publishingLive }) {
  const { mainText, tags } = splitTextAndHashtags(post.text_content, post.hashtags);
  const fullText = tags ? `${mainText}\n\n${tags}` : mainText;
  const charCount = preview?.char_count ?? fullText.length;
  const overLimit = preview?.over_limit ?? charCount > 280;
  const canEdit = post.status === 'draft' || post.status === 'approved';

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="p-4 space-y-3">
        <PostBadges post={post} />

        {/* Source tweet context for replies */}
        {post.reply_to_username && (
          <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
            <div className="text-xs text-gray-500 mb-1">
              Replying to @{post.reply_to_username}
            </div>
            {post.source_tweet_text && (
              <p className="text-xs text-gray-600 line-clamp-2">{post.source_tweet_text}</p>
            )}
          </div>
        )}

        {/* Mock Tweet */}
        <div className="border border-gray-200 rounded-xl p-4">
          <div className="flex gap-3">
            <RigaCapLogo size={40} className="shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1">
                <span className="font-bold text-sm text-gray-900">RigaCap</span>
                <span className="text-sm text-gray-500">@rigacap</span>
              </div>
              <div className="mt-1">
                <InlineEditableText
                  text={mainText}
                  hashtags={tags}
                  postId={post.id}
                  canEdit={canEdit}
                  onEdit={onEdit}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Char Count */}
        <div className="flex items-center justify-between">
          <span className={`text-xs font-medium ${overLimit ? 'text-red-600' : 'text-gray-400'}`}>
            {charCount}/280
          </span>
          <ActionButtons
            post={post}
            actionLoading={actionLoading}
            onApprove={onApprove}
            onReject={onReject}
            onRegenerate={onRegenerate}
            onDelete={onDelete}
            onPublish={onPublish}
            onSchedule={onSchedule}
            onCancel={onCancel}
            publishingLive={publishingLive}
          />
        </div>
      </div>
    </div>
  );
}

function ThreadsCard({ post, actionLoading, onApprove, onReject, onRegenerate, onDelete, onPublish, onEdit, onSchedule, onCancel, publishingLive }) {
  const { mainText, tags } = splitTextAndHashtags(post.text_content, post.hashtags);
  const charCount = (mainText + (tags ? `\n\n${tags}` : '')).length;
  const overLimit = charCount > 500;
  const canEdit = post.status === 'draft' || post.status === 'approved';

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="p-4 space-y-3">
        <PostBadges post={post} />

        {/* Source thread context for replies */}
        {post.reply_to_username && (
          <div className="bg-gray-50 rounded-lg p-3 border border-gray-100">
            <div className="text-xs text-gray-500 mb-1">
              Replying to @{post.reply_to_username}
            </div>
            {post.source_tweet_text && (
              <p className="text-xs text-gray-600 line-clamp-2">{post.source_tweet_text}</p>
            )}
          </div>
        )}

        {/* Mock Threads Post */}
        <div className="border border-gray-200 rounded-xl p-4">
          <div className="flex gap-3">
            <RigaCapLogo size={40} className="shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1">
                <span className="font-bold text-sm text-gray-900">rigacap</span>
                <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">Threads</span>
              </div>
              <div className="mt-1">
                <InlineEditableText
                  text={mainText}
                  hashtags={tags}
                  postId={post.id}
                  canEdit={canEdit}
                  onEdit={onEdit}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Char Count */}
        <div className="flex items-center justify-between">
          <span className={`text-xs font-medium ${overLimit ? 'text-red-600' : 'text-gray-400'}`}>
            {charCount}/500
          </span>
          <ActionButtons
            post={post}
            actionLoading={actionLoading}
            onApprove={onApprove}
            onReject={onReject}
            onRegenerate={onRegenerate}
            onDelete={onDelete}
            onPublish={onPublish}
            onSchedule={onSchedule}
            onCancel={onCancel}
            publishingLive={publishingLive}
          />
        </div>
      </div>
    </div>
  );
}

function InstagramCard({ post, preview, actionLoading, onApprove, onReject, onRegenerate, onDelete, onPublish, onEdit, onSchedule, onCancel, onGenerateChart, publishingLive }) {
  const { mainText, tags } = splitTextAndHashtags(post.text_content, post.hashtags);
  const imageUrl = preview?.image_url || null;
  const hasImage = !!post.image_s3_key || !!imageUrl;
  const chartLoading = actionLoading === 'generate-chart';
  const canGenerateChart = post.post_type === 'trade_result' || post.post_type === 'missed_opportunity';
  const canEdit = post.status === 'draft' || post.status === 'approved';

  const generateChartButton = canGenerateChart && !hasImage && (
    <button
      onClick={() => onGenerateChart(post.id)}
      disabled={!!actionLoading}
      className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-colors disabled:opacity-50"
      title="Generate Chart"
    >
      {chartLoading ? <RefreshCw size={13} className="animate-spin" /> : <BarChart3 size={13} />}
      Chart
    </button>
  );

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="p-4 space-y-3">
        <PostBadges post={post} />

        {/* Mock Instagram Post */}
        <div className="border border-gray-200 rounded-xl overflow-hidden">
          {/* IG Header */}
          <div className="flex items-center gap-2.5 px-3 py-2.5 border-b border-gray-100">
            <RigaCapLogo size={32} className="shrink-0" />
            <span className="font-semibold text-sm text-gray-900">rigacap</span>
          </div>

          {/* Image Area — only show if there's an image or the post type supports chart generation */}
          {imageUrl ? (
            <img
              src={imageUrl}
              alt="Chart card"
              className="w-full aspect-[4/5] object-cover bg-gray-100"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          ) : (canGenerateChart || post.image_s3_key) && (
            <div className="w-full aspect-[4/5] bg-gray-50 flex flex-col items-center justify-center gap-3">
              <Image size={40} className="text-gray-300" />
              {post.image_s3_key ? (
                <span className="text-xs text-gray-400">Image loading...</span>
              ) : (
                <button
                  onClick={() => onGenerateChart(post.id)}
                  disabled={!!actionLoading}
                  className="px-4 py-2 text-sm font-medium text-indigo-700 bg-indigo-100 hover:bg-indigo-200 rounded-lg transition-colors disabled:opacity-50"
                >
                  {chartLoading ? (
                    <span className="flex items-center gap-2"><RefreshCw size={14} className="animate-spin" /> Generating...</span>
                  ) : (
                    'Generate Chart'
                  )}
                </button>
              )}
            </div>
          )}

          {/* Caption */}
          <div className="px-3 py-2.5">
            <div className="text-sm text-gray-900">
              <span className="font-semibold">rigacap</span>{' '}
              <InlineEditableText
                text={mainText}
                hashtags={tags}
                postId={post.id}
                canEdit={canEdit}
                onEdit={onEdit}
              />
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end">
          <ActionButtons
            post={post}
            actionLoading={actionLoading}
            onApprove={onApprove}
            onReject={onReject}
            onRegenerate={onRegenerate}
            onDelete={onDelete}
            onPublish={onPublish}
            onSchedule={onSchedule}
            onCancel={onCancel}
            publishingLive={publishingLive}
            extraButtons={generateChartButton}
          />
        </div>
      </div>
    </div>
  );
}

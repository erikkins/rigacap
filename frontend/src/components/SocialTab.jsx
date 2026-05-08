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
  { id: 'monthly_recap', label: 'Monthly Recap' },
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
  monthly_recap: 'bg-violet-100 text-violet-700',
  contextual_reply: 'bg-cyan-100 text-cyan-700',
  instagram_comment_reply: 'bg-pink-100 text-pink-700',
  manual: 'bg-indigo-100 text-indigo-700',
};

const TYPE_LABELS = {
  trade_result: 'Trade Result',
  missed_opportunity: 'Missed Opportunity',
  weekly_recap: 'Weekly Recap',
  regime_commentary: 'Regime',
  monthly_recap: 'Monthly Recap',
  contextual_reply: 'Reply',
  instagram_comment_reply: 'IG Comment',
  manual: 'Manual',
};

function RigaCapLogo({ size = 40, className = '' }) {
  return <img src="/icon-halo.svg" alt="RigaCap" width={size} height={size} className={className} />;
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
    label: 'Now Live',
    imageUrl: '/launch-cards/launch-1.png',
    twitter: {
      text: "RigaCap is live.\n\nA disciplined momentum strategy for the investor who already knows enough to follow signals \u2014 but doesn't have the time to build the system that generates them.\n\nStays in cash when it should. Exits before major drawdowns.\n\nrigacap.com",
      hashtags: '',
    },
    instagram: {
      text: "RigaCap is live.\n\nIt is built for the investor who already knows enough to follow signals. Trailing stops, regime awareness, position sizing \u2014 these are not novel ideas. The hard part is operating them with discipline, every day, without flinching.\n\nThat's what RigaCap does. The system stays in cash when conditions deteriorate. Exits before major drawdowns. Sends 3 to 4 signals a month, sometimes zero. Most months, that is the right answer.\n\nNo minimums. No performance fees. Same signals for everyone, whether you put in $5k or $500k.\n\nrigacap.com",
      hashtags: '#investing #momentum #disciplinedtrading #rigacap',
    },
    threads: {
      text: "RigaCap is live.\n\nBuilt for the investor who already knows enough to follow signals \u2014 but doesn't have time to build the system that generates them.\n\nStays in cash when it should. Exits before major drawdowns. 3 to 4 signals a month, sometimes zero.\n\nrigacap.com",
    },
  },
  {
    id: 'launch-2',
    label: 'No Cherry-Picking',
    imageUrl: '/launch-cards/launch-2.png',
    twitter: {
      text: "Most backtests cherry-pick the start date that flatters them. We published all of ours.\n\nWorst: +109%\nAverage: +160%\nBest: +252%\nMax drawdown: 20.4%\n\nFive years. Every start date positive \u2014 including the one that began before the 2022 bear.\n\nrigacap.com/track-record",
      hashtags: '',
    },
    instagram: {
      text: "Most backtests show you the result that flatters the strategy. A single start date, the one where the numbers work.\n\nWe published all of ours.\n\nFive-year walk-forward, multiple start dates, no cherry-picking:\n\nWorst: +109%\nAverage: +160%\nBest: +252%\nMax drawdown: 20.4%\n\nEvery start date positive. Including the one that began before the 2022 bear market \u2014 the year the S&P fell 20%.\n\nFull methodology published on the track record page, exactly as the strategy ran. No omissions.\n\nrigacap.com/track-record",
      hashtags: '#investing #backtest #walkforward #trackrecord #rigacap',
    },
    threads: {
      text: "Most backtests cherry-pick the start date that flatters the strategy.\n\nWe published all of ours.\n\nWorst: +109%\nAverage: +160%\nBest: +252%\nMax drawdown: 20.4%\n\nEvery start date positive \u2014 including the one that began before the 2022 bear.\n\nFull methodology published.\n\nrigacap.com/track-record",
    },
  },
  {
    id: 'launch-3',
    label: 'Three-Factor Ensemble',
    imageUrl: '/launch-cards/launch-3.png',
    twitter: {
      text: "Three things have to align before RigaCap signals a buy:\n\nI. Timing \u2014 proprietary breakout trigger\nII. Quality \u2014 leading momentum across the universe\nIII. Risk \u2014 market regime permits exposure\n\nWhen they don't align, the system stays quiet. Most months, that is the right answer.",
      hashtags: '',
    },
    instagram: {
      text: "A signal is not a single indicator firing. It is a coincidence of three.\n\nI. TIMING. A proprietary breakout trigger has confirmed.\n\nII. QUALITY. The stock leads its universe on momentum. Trend, not noise.\n\nIII. RISK. The market regime \u2014 one of seven the system reads \u2014 permits new exposure. In a panic regime, no entries fire. In strong bull, full sizing.\n\nWhen all three align, RigaCap signals. When they don't, it does nothing.\n\nMost months, that is the right answer.\n\nrigacap.com",
      hashtags: '#investing #ensemble #systematictrading #rigacap',
    },
    threads: {
      text: "Three things have to align before RigaCap signals a buy.\n\nI. Timing \u2014 proprietary breakout trigger\nII. Quality \u2014 leading momentum across the universe\nIII. Risk \u2014 market regime permits exposure\n\nWhen they don't align, the system stays quiet. Most months, that is the right answer.\n\nrigacap.com",
    },
  },
  {
    id: 'launch-4',
    label: 'Seven Regimes',
    imageUrl: '/launch-cards/launch-4.png',
    twitter: {
      text: "The market doesn't have one mode. It has seven.\n\nStrong Bull. Weak Bull. Rotating Bull.\nRange Bound. Weak Bear. Panic.\nRecovery.\n\nRigaCap reads which one you're in and adjusts position sizing, stops, and signal sensitivity automatically.\n\nCash is a position too.",
      hashtags: '',
    },
    instagram: {
      text: "The market does not have one mode. It has seven.\n\nStrong Bull \u2014 broad rally, full exposure.\nWeak Bull \u2014 advancing on narrow leadership.\nRotating Bull \u2014 sector rotation driving gains.\nRange Bound \u2014 sideways, low conviction.\nWeak Bear \u2014 declining with selling pressure.\nPanic / Crash \u2014 sharp selloff, system moves to cash.\nRecovery \u2014 rebounding from recent lows.\n\nThe system reads daily which regime is active. Position sizing, stop levels, and signal sensitivity adjust automatically. In panic, no new entries. In strong bull, full size.\n\nA strategy that performs in one regime and fails in another is not a strategy. It is luck.\n\nCash is a position too.\n\nrigacap.com",
      hashtags: '#investing #marketregime #riskmanagement #rigacap',
    },
    threads: {
      text: "The market does not have one mode. It has seven.\n\nStrong Bull. Weak Bull. Rotating Bull. Range Bound. Weak Bear. Panic. Recovery.\n\nRigaCap reads which one you're in and adjusts position sizing, stops, and signal sensitivity automatically.\n\nCash is a position too.\n\nrigacap.com",
    },
  },
  {
    id: 'launch-5',
    label: 'External Discipline',
    imageUrl: '/launch-cards/launch-5.png',
    twitter: {
      text: "You can find signals anywhere. Discipline is harder.\n\nSitting in cash when nothing's working. Honoring stops without second-guessing. Not doubling down on losers.\n\nRigaCap is an external discipline layer.\n\n$59/mo founding rate (first 100). 7-day trial.\n\nrigacap.com",
      hashtags: '',
    },
    instagram: {
      text: "You can find signals anywhere. The internet is full of them.\n\nWhat is harder to find is the discipline to follow them. To sit in cash when nothing is working. To honor a stop without second-guessing it. To not double down on a losing position because the chart looks oversold.\n\nRigaCap is an external discipline layer. The system tells you when to enter, when to exit, and \u2014 just as importantly \u2014 when to do nothing.\n\nFounding rate: $59 per month for the first 100 members.\nStandard: $129 per month.\nAnnual: $1,099 (three months free).\nTrial: 7 days, full access.\n\nrigacap.com",
      hashtags: '#investing #disciplinedtrading #signals #rigacap',
    },
    threads: {
      text: "You can find signals anywhere. Discipline is harder.\n\nSitting in cash when nothing's working. Honoring stops without second-guessing. Not doubling down on losers.\n\nRigaCap is an external discipline layer.\n\n$59/mo founding rate, first 100 members. 7-day trial.\n\nrigacap.com",
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
              image_s3_key: lp.imageUrl ? `social/images/${lp.imageUrl.split('/').pop()}` : undefined,
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
                <div className="flex items-start gap-3">
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
  const canModify = post.status === 'draft' || post.status === 'rejected' || post.status === 'scheduled' || post.status === 'posted';

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
          <div className="flex items-start gap-3">
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
          <div className="flex items-start gap-3">
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

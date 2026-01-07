import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import html2canvas from 'html2canvas';
import {
  Send, Settings, User, Bot, Trash2, Loader2, StopCircle,
  Sparkles, MessageSquare, MessageSquarePlus, Columns2, Plus, History,
  Image as ImageIcon, BarChart2, Globe, Code, Copy, Check,
  Search, Zap, Terminal, CheckCircle2, ArrowRight, Download, ArrowUp,
  TrendingUp, Flame, Newspaper, Activity, LogOut, LogIn,
  MoreVertical, Edit3, X, AlertTriangle
} from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { v4 as uuidv4 } from 'uuid';
import { AuthProvider, useAuth } from './context/AuthContext';
import AuthModal from './components/AuthModal';
import SettingsModal from './components/SettingsModal';
import StrategyNexus from './components/StrategyNexus';
import DailyReport from './components/DailyReport';
import PrivacyPolicy from './components/PrivacyPolicy';
import TermsOfService from './components/TermsOfService';
import LandingPage from './components/LandingPage';
import TerminalLoader from './components/TerminalLoader';
import HomePage from './components/HomePage';

// Import from new modular structure
import { AGENT_ID, AGENT_ANALYST_ID, AGENT_TRADER_ID, BASE_URL, dashboardApi, sessionApi, creditsApi, dashboardCache } from './services';
import { COIN_DATA, detectCoinsFromText, formatPrice, getOrCreateTempUserId } from './utils';
import { QuickPrompts, QuickPromptsPills, LatestNews, PopularTokens, KeyIndicators, TrendingBar, SuggestedQuestion } from './components/dashboard';
import { ToolStep, CoinButton, CoinButtonBar } from './components/chat';


function AppContent() {
  // --- i18n ---
  const { t, i18n } = useTranslation();

  // --- Auth ---
  const { user, loading: authLoading, signOut } = useAuth();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [creditsHistory, setCreditsHistory] = useState([]);
  const [showStrategyNexus, setShowStrategyNexus] = useState(false);
  const [showDailyReport, setShowDailyReport] = useState(false);

  // Use authenticated user ID or temp ID
  const userId = user?.id || getOrCreateTempUserId();

  // --- State ---
  const [messages, setMessages] = useState([]); // Empty initially to show Home View
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false); // Show "thinking" indicator between tool calls
  const [sessions, setSessions] = useState([]);
  const [toolStartTimes, setToolStartTimes] = useState({}); // Track tool start times: { toolKey: timestamp }
  const [credits, setCredits] = useState(null); // User credits
  const [checkedInToday, setCheckedInToday] = useState(false); // Daily check-in status
  const [toast, setToast] = useState(null); // Toast notification: { message, type }

  // Agent Mode State - 'analyst' (default) or 'trader'
  const [selectedAgent, setSelectedAgent] = useState('analyst');
  const [agentMenuOpen, setAgentMenuOpen] = useState(false);

  // Workspace State
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [activeChart, setActiveChart] = useState(null); // { symbol: 'BTCUSDT', name: 'Bitcoin' }
  const [detectedCoins, setDetectedCoins] = useState([]); // ['BTC', 'ETH', 'SOL']

  // UI State
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);

  // Session State
  const [sessionId, setSessionId] = useState(uuidv4());

  // Session Management State
  const [sessionMenuOpen, setSessionMenuOpen] = useState(null); // session_id of open menu
  const [renameDialogOpen, setRenameDialogOpen] = useState(null); // session to rename
  const [renameInput, setRenameInput] = useState('');
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(null); // session to delete

  // Dashboard State (Home View)
  const [dashboardNews, setDashboardNews] = useState([]);
  const [dashboardTokens, setDashboardTokens] = useState([]);
  const [dashboardFearGreed, setDashboardFearGreed] = useState({ value: 50, classification: 'Neutral' });
  const [dashboardIndicators, setDashboardIndicators] = useState([]);
  const [dashboardLoading, setDashboardLoading] = useState(true); // Loading state for skeleton

  // Trending State (lifted from TrendingBar for caching) - read from localStorage on init
  const [trendingTokens, setTrendingTokens] = useState(() => {
    try {
      const cached = localStorage.getItem('trendingTokens');
      if (cached) {
        const { data, timestamp } = JSON.parse(cached);
        // Use cache if less than 10 minutes old
        if (Date.now() - timestamp < 10 * 60 * 1000) {
          return data;
        }
      }
    } catch (e) { }
    return [];
  });
  const [trendingLoading, setTrendingLoading] = useState(() => {
    // If we have cached data, don't show loading
    try {
      const cached = localStorage.getItem('trendingTokens');
      if (cached) {
        const { data } = JSON.parse(cached);
        return !data || data.length === 0;
      }
    } catch (e) { }
    return true;
  });

  // Fetch credits and check-in status when user logs in
  useEffect(() => {
    if (user?.id) {
      // Fetch credits
      fetch(`${BASE_URL}/api/credits/${user.id}`)
        .then(res => res.json())
        .then(data => setCredits(data.credits))
        .catch(console.error);
      // Fetch check-in status
      fetch(`${BASE_URL}/api/credits/${user.id}/checkin-status`)
        .then(res => res.json())
        .then(data => setCheckedInToday(data.checked_in_today))
        .catch(console.error);
    } else {
      setCredits(null);
      setCheckedInToday(false);
    }
  }, [user]);

  // Ensure userId is saved (double check)
  useEffect(() => {
    if (userId) {
      localStorage.setItem('agno_user_id', userId);
    }
  }, [userId]);

  // Fetch credits history when settings modal opens
  useEffect(() => {
    if (showSettingsModal && user) {
      fetch(`${BASE_URL}/api/credits/${userId}/history?limit=50`)
        .then(r => r.json())
        .then(data => setCreditsHistory(data.history || []))
        .catch(console.error);
    }
  }, [showSettingsModal, userId, user]);

  // Fetch dashboard data on mount with cache-first strategy
  useEffect(() => {
    const startTime = performance.now();

    // Helper: fetch with timeout
    const fetchWithTimeout = async (url, timeout = 5000, fallback = {}) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);
      try {
        const res = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        return await res.json();
      } catch (e) {
        clearTimeout(timeoutId);
        console.warn(`[Dashboard] Timeout or error for ${url}:`, e.message);
        return fallback;
      }
    };

    // Phase 1: Load from cache immediately (instant render)
    const loadFromCache = () => {
      const cachedNews = dashboardCache.getCache('news');
      const cachedTokens = dashboardCache.getCache('tokens');
      const cachedFearGreed = dashboardCache.getCache('fearGreed');
      const cachedIndicators = dashboardCache.getCache('indicators');
      const cachedTrending = dashboardCache.getCache('trending');

      let hasAnyCache = false;

      if (cachedNews?.data?.length > 0) {
        setDashboardNews(cachedNews.data);
        hasAnyCache = true;
      }
      if (cachedTokens?.data?.length > 0) {
        setDashboardTokens(cachedTokens.data);
        hasAnyCache = true;
      }
      if (cachedFearGreed?.data) {
        setDashboardFearGreed(cachedFearGreed.data);
        hasAnyCache = true;
      }
      if (cachedIndicators?.data?.length > 0) {
        setDashboardIndicators(cachedIndicators.data);
        hasAnyCache = true;
      }
      if (cachedTrending?.data?.length > 0) {
        setTrendingTokens(cachedTrending.data);
        setTrendingLoading(false);
        hasAnyCache = true;
      }

      // If we have any cache, hide skeleton immediately
      if (hasAnyCache) {
        setDashboardLoading(false);
        console.log(`[Dashboard] Cache loaded in ${(performance.now() - startTime).toFixed(0)}ms`);
      }

      return hasAnyCache;
    };

    // Phase 2: Background refresh (silent update)
    const refreshFromAPI = async () => {
      const [newsRes, tokensRes, fearGreedRes, indicatorsRes, trendingRes] = await Promise.all([
        fetchWithTimeout(`${BASE_URL}/api/dashboard/news`, 8000, { news: [] }),
        fetchWithTimeout(`${BASE_URL}/api/dashboard/tokens`, 5000, { tokens: [] }),
        fetchWithTimeout(`${BASE_URL}/api/dashboard/fear-greed`, 5000, { value: 50, classification: 'Neutral' }),
        fetchWithTimeout(`${BASE_URL}/api/dashboard/indicators`, 8000, { indicators: [] }),
        fetchWithTimeout(`${BASE_URL}/api/dashboard/trending?limit=10`, 5000, { tokens: [] })
      ]);

      // Update state and cache
      if (newsRes.news?.length > 0) {
        setDashboardNews(newsRes.news);
        dashboardCache.setCache('news', newsRes.news);
      }
      if (tokensRes.tokens?.length > 0) {
        setDashboardTokens(tokensRes.tokens);
        dashboardCache.setCache('tokens', tokensRes.tokens);
      }
      if (fearGreedRes.value !== undefined) {
        setDashboardFearGreed(fearGreedRes);
        dashboardCache.setCache('fearGreed', fearGreedRes);
      }
      if (indicatorsRes.indicators?.length > 0) {
        setDashboardIndicators(indicatorsRes.indicators);
        dashboardCache.setCache('indicators', indicatorsRes.indicators);
      }

      setDashboardLoading(false);

      // Update trending
      const trendingData = trendingRes.tokens || [];
      if (trendingData.length > 0) {
        setTrendingTokens(trendingData);
        setTrendingLoading(false);
        dashboardCache.setCache('trending', trendingData);
      } else {
        setTrendingLoading(false);
      }

      console.log(`[Dashboard] API refresh completed in ${(performance.now() - startTime).toFixed(0)}ms`);
    };

    // Execute: cache first, then refresh
    const hasCache = loadFromCache();

    // Always refresh in background, but with slight delay if we have cache
    if (hasCache) {
      // Delay refresh slightly to not compete with initial render
      setTimeout(refreshFromAPI, 100);
    } else {
      // No cache, refresh immediately
      refreshFromAPI();
    }

    // Token refresh every 1 minute (priority data)
    const tokenInterval = setInterval(async () => {
      try {
        const res = await fetch(`${BASE_URL}/api/dashboard/tokens`);
        const data = await res.json();
        if (data.tokens?.length > 0) {
          setDashboardTokens(data.tokens);
          dashboardCache.setCache('tokens', data.tokens);
        }
      } catch (e) { console.error('[Dashboard] Token refresh error:', e); }
    }, 60000);

    // News and indicators refresh every 10 minutes
    const otherInterval = setInterval(async () => {
      try {
        const [newsRes, indicatorsRes] = await Promise.all([
          fetch(`${BASE_URL}/api/dashboard/news`).then(r => r.json()),
          fetch(`${BASE_URL}/api/dashboard/indicators`).then(r => r.json())
        ]);
        if (newsRes.news?.length > 0) {
          setDashboardNews(newsRes.news);
          dashboardCache.setCache('news', newsRes.news);
        }
        if (indicatorsRes.indicators?.length > 0) {
          setDashboardIndicators(indicatorsRes.indicators);
          dashboardCache.setCache('indicators', indicatorsRes.indicators);
        }
      } catch (e) { console.error('[Dashboard] Other refresh error:', e); }
    }, 600000);

    // Trending refresh every 5 minutes
    const trendingInterval = setInterval(async () => {
      try {
        const res = await fetch(`${BASE_URL}/api/dashboard/trending?limit=10`);
        const data = await res.json();
        const tokens = data.tokens || [];
        if (tokens.length > 0) {
          setTrendingTokens(tokens);
          dashboardCache.setCache('trending', tokens);
        }
      } catch (e) { console.error('[Dashboard] Trending refresh error:', e); }
    }, 300000);

    return () => {
      clearInterval(tokenInterval);
      clearInterval(otherInterval);
      clearInterval(trendingInterval);
    };
  }, []);

  // --- Refs ---
  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  const inputRef = useRef(null);
  const userMenuRef = useRef(null);

  // Auto-resize input when content changes (handles programmatic updates)
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = '48px';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  // 点击外部关闭用户菜单
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setShowUserMenu(false);
      }
    };

    if (showUserMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showUserMenu]);

  // 点击外部关闭 session 菜单
  useEffect(() => {
    const handleClickOutside = (e) => {
      // Check if click is inside session menu
      const sessionMenu = document.querySelector('[data-session-menu]');
      if (sessionMenu && sessionMenu.contains(e.target)) {
        return; // Don't close if clicked inside menu
      }
      setSessionMenuOpen(null);
    };

    if (sessionMenuOpen) {
      // 延迟添加事件监听，避免立即触发
      const timer = setTimeout(() => {
        document.addEventListener('click', handleClickOutside);
      }, 10);
      return () => {
        clearTimeout(timer);
        document.removeEventListener('click', handleClickOutside);
      };
    }
  }, [sessionMenuOpen]);

  // --- Effects ---
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // --- API Calls ---
  const fetchSessions = useCallback(async (retryCount = 0) => {
    // Skip if auth is still loading
    if (authLoading) {
      console.log('[Sessions] Waiting for auth...');
      return;
    }

    try {
      console.log(`[Sessions] Fetching for user: ${userId}`);
      const res = await fetch(`${BASE_URL}/api/sessions?user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
        console.log(`[Sessions] Loaded ${data.sessions?.length || 0} sessions`);
      } else {
        console.error('[Sessions] API error:', res.status);
        // Retry on failure
        if (retryCount < 2) {
          setTimeout(() => fetchSessions(retryCount + 1), 1000);
        }
      }
    } catch (e) {
      console.error("[Sessions] Failed to fetch:", e);
      // Retry on network error
      if (retryCount < 2) {
        setTimeout(() => fetchSessions(retryCount + 1), 1000);
      }
    }
  }, [userId, authLoading]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Fetch sessions when auth is ready or user changes
  useEffect(() => {
    inputRef.current?.focus();
    if (!authLoading && userId) {
      fetchSessions();
    }
  }, [fetchSessions, authLoading, userId]);



  const loadSession = async (sid) => {
    try {
      setIsLoading(true);
      const res = await fetch(`${BASE_URL}/api/history?session_id=${sid}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages);
        setSessionId(sid);
        setShowMobileSidebar(false);
        setShowStrategyNexus(false); // Exit Strategy Nexus view
        setShowDailyReport(false); // Exit Daily Report view

        // Dynamic coin detection from last assistant message
        const lastAssistant = data.messages.filter(m => m.role === 'assistant').pop();
        if (lastAssistant?.content) {
          const coins = detectCoinsFromText(lastAssistant.content);
          setDetectedCoins(coins);
        } else {
          setDetectedCoins([]);
        }
      }
    } catch (e) {
      console.error("Failed to load session:", e);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Handlers ---
  const handleSend = async (txt = input) => {
    if (!txt.trim() || isLoading) return;

    // Check if user is logged in
    if (!user) {
      setShowAuthModal(true);
      return;
    }

    // Check if user has enough credits (minimum 5)
    try {
      const creditCheck = await fetch(`${BASE_URL}/api/credits/${userId}/can-chat`);
      if (creditCheck.ok) {
        const data = await creditCheck.json();
        if (!data.can_chat) {
          setToast({
            message: `${t('credits.insufficientMessage')} (${t('credits.current')}: ${data.credits})`,
            type: 'error'
          });
          setTimeout(() => setToast(null), 5000);
          return;
        }
      }
    } catch (e) {
      console.error("Credit check failed:", e);
      // Continue anyway if credit check fails
    }

    const userMessage = txt.trim();
    setInput('');

    // Optimistic update
    const newMessages = [...messages, { role: 'user', content: userMessage }];
    setMessages(newMessages);
    setMessages(prev => [...prev, { role: 'assistant', content: '' }]);
    setIsLoading(true);

    abortControllerRef.current = new AbortController();

    try {
      const params = new URLSearchParams();
      params.append('message', userMessage);
      params.append('stream', 'True');
      params.append('user_id', userId);
      params.append('session_id', sessionId);

      // Dynamic Agent ID based on selected mode
      const activeAgentId = selectedAgent === 'trader' ? AGENT_TRADER_ID : AGENT_ANALYST_ID;

      const response = await fetch(`${BASE_URL}/agents/${activeAgentId}/runs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: params,
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) throw new Error(response.statusText);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';
      let buffer = '';
      let currentEvent = null;
      const activeTools = {}; // Track active tool calls: { toolCallId: { name, startTime } }
      let runMetrics = null; // Store metrics from RunCompleted event

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmedLine = line.trim();
          if (!trimmedLine) continue;

          // Parse SSE format: "event: EventName" or "data: {...}"
          if (trimmedLine.startsWith('event:')) {
            currentEvent = trimmedLine.replace('event:', '').trim();
            continue;
          }

          if (trimmedLine.startsWith('data:')) {
            try {
              const jsonStr = trimmedLine.replace('data:', '').trim();
              const data = JSON.parse(jsonStr);

              // Handle different event types
              if (currentEvent === 'ToolCallStarted' || data.event === 'ToolCallStarted') {
                // Tool call started - show immediately with live timer
                const toolName = data.tool?.tool_name || 'tool';
                const toolCallId = data.tool?.tool_call_id || toolName;
                const now = Date.now();

                activeTools[toolCallId] = { name: toolName, startTime: now };
                setToolStartTimes(prev => ({ ...prev, [toolName]: now }));

                // Add tool call to message immediately (mark as running)
                const toolLine = `\n${toolName}(...)`;
                assistantMessage += toolLine;
                setIsThinking(false); // Tool started, not thinking
                setMessages(prev => {
                  const newMsgs = [...prev];
                  const lastMsg = newMsgs[newMsgs.length - 1];
                  lastMsg.content = assistantMessage;
                  return newMsgs;
                });
              } else if (currentEvent === 'ToolCallCompleted' || data.event === 'ToolCallCompleted') {
                // Tool call completed - update with precise time
                const toolName = data.tool?.tool_name || 'tool';
                const toolCallId = data.tool?.tool_call_id || toolName;
                const duration = data.tool?.metrics?.duration || 0;

                // Replace the running tool line with completed version
                // Use a more robust pattern that escapes special chars
                const escapedName = toolName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const runningPattern = new RegExp(`\\n${escapedName}\\(\\.\\.\\.\\)(?!.*completed)`, 'g');
                const completedLine = `\n${toolName}(...) completed in ${duration.toFixed(4)}s.`;

                // Only replace if pattern found
                if (assistantMessage.match(runningPattern)) {
                  assistantMessage = assistantMessage.replace(runningPattern, completedLine);
                }

                setMessages(prev => {
                  const newMsgs = [...prev];
                  const lastMsg = newMsgs[newMsgs.length - 1];
                  lastMsg.content = assistantMessage;
                  return newMsgs;
                });

                // Remove from active tools and show thinking
                delete activeTools[toolCallId];
                setIsThinking(true); // Tool completed, waiting for next action
              } else if (currentEvent === 'RunCompleted' || data.event === 'RunCompleted') {
                // Extract metrics from RunCompleted event for token credit deduction
                if (data.metrics) {
                  runMetrics = data.metrics;
                }
                setIsThinking(false); // Run completed, stop thinking
              } else if (data.content) {
                // Regular content update (RunContent events)
                setIsThinking(false); // Got content, not thinking
                assistantMessage += data.content;
                setMessages(prev => {
                  const newMsgs = [...prev];
                  const lastMsg = newMsgs[newMsgs.length - 1];
                  lastMsg.content = assistantMessage;
                  return newMsgs;
                });
              }

              currentEvent = null; // Reset for next event
            } catch {
              // Ignore parse errors
            }
          }
        }
      }

      // Refresh sessions list after chat
      fetchSessions();

      // Count completed tool calls from activeTools and deduct credits
      // Note: activeTools is emptied during processing, so we count from toolStartTimes
      // We need to use a different approach - count from the message content
      const toolMatches = assistantMessage.match(/completed in \d+\.\d+s\./g);
      const actualToolCount = toolMatches ? toolMatches.length : 0;

      // Deduct credits based on token usage (5万 tokens = 1 credit)
      // Use metrics from RunCompleted event
      if (runMetrics?.total_tokens > 0 && user?.id) {
        try {
          const res = await fetch(`${BASE_URL}/api/credits/${user.id}/deduct-tokens`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              total_tokens: runMetrics.total_tokens,
              session_id: sessionId
            })
          });
          if (res.ok) {
            const data = await res.json();
            setCredits(data.current_credits);
            console.log(`[TokenCredit] ${runMetrics.total_tokens.toLocaleString()} tokens -> -${data.deducted} credits`);
          }
        } catch (e) {
          console.error('Failed to deduct token credits:', e);
        }
      }

      // Clear tool start times for next chat
      setToolStartTimes({});

      // Detect coins from the final message content
      setMessages(prev => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg?.role === 'assistant' && lastMsg?.content) {
          const coins = detectCoinsFromText(lastMsg.content);
          setDetectedCoins(coins);
        }
        return prev;
      });

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Stream stopped by user');
      } else {
        console.error('Error:', error);
        setMessages(prev => {
          const newMsgs = [...prev];
          const lastMsg = newMsgs[newMsgs.length - 1];
          if (lastMsg.role === 'assistant') {
            lastMsg.content += `\n\n❌ **Error:** ${error.message}`;
          }
          return newMsgs;
        });
      }
    } finally {
      setIsLoading(false);
      setIsThinking(false); // Clear thinking state
      abortControllerRef.current = null;
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsLoading(false);
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setSessionId(uuidv4());
    setShowMobileSidebar(false);
    setInput('');
    setDetectedCoins([]); // Clear detected coins
    setWorkspaceOpen(false); // Close workspace
    setActiveChart(null);
    setShowStrategyNexus(false); // Exit Strategy Nexus view
    setShowDailyReport(false); // Exit Daily Report view
    setSelectedAgent('analyst'); // Reset to default analyst mode
  };

  // Session management handlers
  const handleRenameSession = async (sid) => {
    if (!renameInput.trim()) return;
    try {
      const res = await fetch(`${BASE_URL}/api/sessions/${sid}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: renameInput.trim() })
      });
      if (res.ok) {
        fetchSessions();
        setRenameDialogOpen(null);
        setRenameInput('');
      }
    } catch (e) {
      console.error('Failed to rename session:', e);
    }
  };

  const handleDeleteSession = async (sid) => {
    try {
      const res = await fetch(`${BASE_URL}/api/sessions/${sid}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        fetchSessions();
        setDeleteConfirmOpen(null);
        // If deleted current session, start new chat
        if (sid === sessionId) {
          startNewChat();
        }
      }
    } catch (e) {
      console.error('Failed to delete session:', e);
    }
  };

  // Handle coin button click - open TradingView chart
  const handleCoinClick = (coin) => {
    const data = COIN_DATA[coin];
    if (!data) return;

    setActiveChart({ symbol: data.symbol, name: data.name, coin });
    setWorkspaceOpen(true);
    setIsSidebarOpen(false); // Collapse sidebar when workspace opens
  };

  // Close workspace panel
  const handleCloseWorkspace = () => {
    setWorkspaceOpen(false);
    setActiveChart(null);
  };

  // Export message as image
  const exportAsImage = async (messageId) => {
    const element = document.getElementById(`message-${messageId}`);
    if (!element) return;

    try {
      const canvas = await html2canvas(element, {
        backgroundColor: '#ffffff',
        scale: 2, // Higher quality
        useCORS: true,
        logging: false,
      });

      const link = document.createElement('a');
      const timestamp = new Date().toISOString().slice(0, 10);
      link.download = `alpha-analysis-${timestamp}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    } catch (error) {
      console.error('Export failed:', error);
    }
  };

  // --- Components ---

  const SuggestionChip = ({ icon: Icon, label, prompt }) => (
    <button
      onClick={() => handleSend(prompt)}
      className="flex items-center gap-2 px-4 py-2 bg-[#131722] hover:bg-slate-700 text-slate-200 rounded-full text-sm transition-colors"
    >
      <Icon className="w-4 h-4 text-purple-400" />
      <span>{label}</span>
    </button>
  );

  // TradingView Widget component - using direct chart URL
  const TradingViewWidget = ({ symbol, onClose }) => {
    // Use TradingView's direct chart URL format
    const symbolForUrl = symbol?.replace(':', '-') || 'BINANCE-BTCUSDT';
    const chartUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol || 'BINANCE:BTCUSDT')}&interval=D&theme=dark`;

    return (
      <div className="h-full flex flex-col bg-black">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-black">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-slate-400" />
            <span className="font-medium text-white">{symbol?.split(':')[1] || symbol}</span>
            <a
              href={chartUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-slate-400 hover:text-white hover:underline ml-2"
            >
              {t('tool.openInNewTab')}
            </a>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-700 transition-colors"
            title={t('tool.closeChart')}
          >
            <StopCircle className="w-5 h-5 text-slate-400" />
          </button>
        </div>
        {/* Chart container - iframe embed with TradingView widget */}
        <div className="flex-1 relative">
          <iframe
            src={`https://www.tradingview.com/widgetembed/?hideideas=1&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%5D&locale=zh_CN#%7B%22symbol%22%3A%22${encodeURIComponent(symbol || 'BINANCE:BTCUSDT')}%22%2C%22frameElementId%22%3A%22tradingview_widget%22%2C%22interval%22%3A%22D%22%2C%22hide_side_toolbar%22%3A%220%22%2C%22allow_symbol_change%22%3A%221%22%2C%22save_image%22%3A%221%22%2C%22studies%22%3A%5B%5D%2C%22theme%22%3A%22dark%22%2C%22style%22%3A%221%22%2C%22timezone%22%3A%22Asia%2FShanghai%22%7D`}
            style={{ width: '100%', height: '100%', border: 'none' }}
            allowFullScreen
            title={t('common.tradingViewChart')}
            sandbox="allow-same-origin allow-scripts allow-popups allow-forms"
          />
        </div>
      </div>
    );
  };

  // --- Tool UI Components ---
  // --- Tool UI Components (imported from components/chat) ---
  const GroupBlock = ({ textParts, tools, toolStartTimes, blockId, isLastTextBlock }) => {
    // Only show export button for the last text-only block (final analysis result)
    const showExport = isLastTextBlock;

    const handleExport = async () => {
      const element = document.getElementById(`group-block-${blockId}`);
      if (!element) return;

      try {
        const canvas = await html2canvas(element, {
          backgroundColor: '#ffffff',
          scale: 2,
          useCORS: true,
          logging: false,
        });

        const link = document.createElement('a');
        const timestamp = new Date().toISOString().slice(0, 10);
        link.download = `alpha-analysis-${timestamp}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
      } catch (error) {
        console.error('Export failed:', error);
      }
    };

    return (
      <div
        id={`group-block-${blockId}`}
        className="relative group bg-[#131722] rounded-2xl px-5 py-4 text-white animate-in fade-in slide-in-from-bottom-1 duration-300 mb-2"
      >
        {/* Export button for result blocks */}
        {showExport && (
          <button
            onClick={handleExport}
            className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-2 bg-slate-700 rounded-lg hover:bg-slate-600"
            title={t('common.exportImage')}
          >
            <Download className="w-4 h-4 text-slate-300 hover:text-white" />
          </button>
        )}

        {textParts.length > 0 && (
          <div className="w-full overflow-hidden mb-3 last:mb-0">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={MarkdownComponents}
            >
              {textParts.join('\n')}
            </ReactMarkdown>
          </div>
        )}
        {tools.length > 0 && (
          <div className="flex flex-col gap-1 mt-3 pt-3">
            {tools.map((tool, idx) => {
              // Generate a stable key from tool text
              const toolKey = tool.replace(/\(.*\).*/, '').trim();
              const startTime = toolStartTimes?.[toolKey];
              return <ToolStep key={idx} text={tool} startTime={startTime} />;
            })}
          </div>
        )}
      </div>
    );
  };

  const MessageContent = ({ content, toolStartTimes, messageIndex }) => {
    // Filter out raw tool output that shouldn't be displayed (log_strategy_analysis raw data)
    // These contain position_check=, strategy_decision=, action_taken= etc.
    const filteredContent = content
      .replace(/,\s*(?:market_analysis|position_check|strategy_decision|action_taken)=[^,)]+/g, '')
      .replace(/\(\s*,/g, '(');  // Clean up leftover commas

    // Robust Regex to tokenize content into Text and Tools
    // Updated to support all tool patterns including trading tools
    // For log_strategy_analysis, match until "completed" to handle complex nested content
    const TOKEN_REGEX = /(Running: .*?|Searching .*?|Browsing .*?|log_strategy_analysis\([^)]*\)(?:\s+completed(?:\s+策略执行完成)?(?:\s+in\s+(?:~)?[\d\.]+s\.?)?)?|(?:get_\w+|search_\w+|duckduckgo_\w+|search_exa|search|browse|open_position|close_position|update_stop_loss_take_profit|get_positions_summary|partial_close_position)\([^)]*\)(?:\s+completed(?:\s+in\s+(?:~)?[\d\.]+s\.?)?)?)/g;

    const parts = filteredContent.split(TOKEN_REGEX);

    const groups = [];
    let currentGroup = { textParts: [], tools: [] };

    parts.forEach((part) => {
      const trimmed = part.trim();
      if (!trimmed) return;

      // Skip raw tool output remnants
      if (trimmed.match(/^[,\s]*(?:market_analysis|position_check|strategy_decision|action_taken)=/) ||
        trimmed.match(/^\)\s*completed\s+策略执行完成/)) {
        return;
      }

      // Check if the part matches our tool patterns
      const isTool =
        trimmed.match(/^(?:get_\w+|search_\w+|duckduckgo_\w+|search_exa|search|browse|log_strategy_analysis|open_position|close_position|update_stop_loss_take_profit|get_positions_summary|partial_close_position)\(/) ||
        trimmed.startsWith('Searching') ||
        trimmed.startsWith('Browsing') ||
        trimmed.startsWith('Running');

      if (isTool) {
        currentGroup.tools.push(trimmed);
      } else {
        // If we have tools in the current group and encounter new text, 
        // push the current group and start a new one.
        if (currentGroup.tools.length > 0) {
          groups.push(currentGroup);
          currentGroup = { textParts: [], tools: [] };
        }
        currentGroup.textParts.push(trimmed);
      }
    });

    // Push the last group
    if (currentGroup.textParts.length > 0 || currentGroup.tools.length > 0) {
      groups.push(currentGroup);
    }

    // Find the last text-only block (no tools) with substantial content
    let lastTextBlockIndex = -1;
    for (let i = groups.length - 1; i >= 0; i--) {
      if (groups[i].tools.length === 0 && groups[i].textParts.join('').length > 100) {
        lastTextBlockIndex = i;
        break;
      }
    }

    return (
      <div className="flex flex-col w-full max-w-3xl">
        {groups.map((group, idx) => (
          <GroupBlock
            key={idx}
            blockId={`${messageIndex}-${idx}`}
            textParts={group.textParts}
            tools={group.tools}
            toolStartTimes={toolStartTimes}
            isLastTextBlock={idx === lastTextBlockIndex}
          />
        ))}
      </div>
    );
  };

  const MarkdownComponents = {
    code({ node, inline, className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '');
      const [copied, setCopied] = useState(false);

      const handleCopy = () => {
        navigator.clipboard.writeText(String(children).replace(/\n$/, ''));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      };

      return !inline && match ? (
        <div className="relative group rounded-lg overflow-hidden my-4">
          <div className="flex items-center justify-between px-4 py-2 bg-[#1e1e1e] border-b border-gray-700">
            <span className="text-xs text-gray-400 font-mono">{match[1]}</span>
            <button
              onClick={handleCopy}
              className="p-1.5 hover:bg-gray-700 rounded-md transition-colors text-gray-400 hover:text-white"
              title={t('common.copyCode')}
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={match[1]}
            PreTag="div"
            customStyle={{
              margin: 0,
              borderRadius: 0,
              padding: '1rem',
              fontSize: '0.875rem',
              lineHeight: '1.5',
            }}
            {...props}
          >
            {String(children).replace(/\n$/, '')}
          </SyntaxHighlighter>
        </div>
      ) : (
        <code className="bg-slate-600 text-purple-300 px-1.5 py-0.5 rounded-md text-sm font-mono" {...props}>
          {children}
        </code>
      );
    },
    a: ({ node, ...props }) => (
      <a
        target="_blank"
        rel="noopener noreferrer"
        className="text-purple-400 hover:text-purple-300 hover:underline transition-colors font-medium"
        {...props}
      />
    ),
    ul: ({ node, ...props }) => (
      <ul className="list-disc list-outside ml-6 space-y-1 my-3 text-slate-200" {...props} />
    ),
    ol: ({ node, ...props }) => (
      <ol className="list-decimal list-outside ml-6 space-y-1 my-3 text-slate-200" {...props} />
    ),
    h1: ({ node, ...props }) => (
      <h1 className="text-2xl font-bold text-white mt-6 mb-4 pb-2 border-b border-slate-600" {...props} />
    ),
    h2: ({ node, ...props }) => (
      <h2 className="text-xl font-bold text-white mt-5 mb-3" {...props} />
    ),
    h3: ({ node, ...props }) => (
      <h3 className="text-lg font-semibold text-white mt-4 mb-2" {...props} />
    ),
    blockquote: ({ node, ...props }) => (
      <blockquote className="border-l-4 border-purple-500 pl-4 py-1 my-4 bg-slate-600/50 rounded-r italic text-slate-300" {...props} />
    ),
    table: ({ node, ...props }) => (
      <div className="overflow-x-auto my-4 rounded-lg border border-slate-600">
        <table className="min-w-full divide-y divide-slate-600" {...props} />
      </div>
    ),
    th: ({ node, ...props }) => (
      <th className="bg-slate-600 px-4 py-3 text-left text-xs font-semibold text-slate-300 uppercase tracking-wider" {...props} />
    ),
    td: ({ node, ...props }) => (
      <td className="px-4 py-3 text-sm text-slate-200 border-t border-slate-600" {...props} />
    ),
    p: ({ node, ...props }) => (
      <p className="leading-7 my-3 text-slate-200" {...props} />
    ),
  };

  return (
    <div className="flex h-screen bg-black overflow-hidden font-sans text-slate-100">

      {/* Toast Notification */}
      {toast && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] animate-fade-in">
          <div className={`flex items-center gap-3 px-5 py-3 rounded-xl shadow-2xl border backdrop-blur-sm ${toast.type === 'success'
            ? 'bg-green-500/20 border-green-500/40 text-green-300'
            : toast.type === 'error'
              ? 'bg-red-500/20 border-red-500/40 text-red-300'
              : 'bg-slate-700/80 border-slate-600/50 text-slate-200'
            }`}>
            <span className="text-xl">{toast.type === 'success' ? '🎉' : toast.type === 'error' ? '❌' : 'ℹ️'}</span>
            <span className="font-medium">{toast.message}</span>
          </div>
        </div>
      )}

      {/* Mobile Overlay */}
      {showMobileSidebar && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setShowMobileSidebar(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
            fixed lg:static inset-y-0 left-0 z-50 bg-slate-900 text-slate-300 flex flex-col
            transform transition-all duration-300 ease-in-out
            ${showMobileSidebar ? 'translate-x-0 w-72' : '-translate-x-full w-72'} 
            ${isSidebarOpen ? 'lg:translate-x-0 lg:w-72' : 'lg:translate-x-0 lg:w-16'}
        `}
      >
        {/* Sidebar Header */}
        <div className="h-16 flex items-center justify-between px-3">
          <div className={`flex items-center gap-3 ${!isSidebarOpen && 'lg:justify-center lg:w-full'}`}>
            {/* Logo - 折叠时点击展开 */}
            <div
              className={`relative group ${!isSidebarOpen && 'lg:cursor-pointer'}`}
              onClick={() => {
                if (!isSidebarOpen && window.innerWidth >= 1024) {
                  setIsSidebarOpen(true);
                }
              }}
            >
              <img
                src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
                alt="OG"
                className={`rounded-lg object-contain transition-opacity ${isSidebarOpen ? 'w-10 h-10' : 'lg:w-8 lg:h-8 w-10 h-10 lg:group-hover:opacity-0'}`}
              />
              {/* 折叠状态 hover 显示展开图标 */}
              {!isSidebarOpen && (
                <div className="absolute inset-0 hidden lg:flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <Columns2 className="w-5 h-5 text-slate-300" />
                </div>
              )}
            </div>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsSidebarOpen(!isSidebarOpen);
            }}
            className={`p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors ${!isSidebarOpen && 'lg:hidden'}`}
            title={isSidebarOpen ? t('common.collapseSidebar') : t('common.expandSidebar')}
          >
            <Columns2 className="w-5 h-5" />
          </button>
        </div>

        {/* New Chat */}
        <div className={`${isSidebarOpen ? 'px-2' : 'lg:px-2 px-2'}`}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              startNewChat();
            }}
            className={`w-full flex items-center gap-3 py-3 rounded-lg text-slate-300 hover:bg-slate-800/50 hover:text-white transition-colors ${isSidebarOpen ? 'px-4' : 'lg:justify-center lg:px-0 px-4'}`}
            title={t('common.newChat')}
          >
            <Plus className="w-5 h-5 flex-shrink-0" />
            <span className={`font-medium whitespace-nowrap overflow-hidden transition-all duration-300 ${isSidebarOpen ? 'opacity-100 max-w-[200px]' : 'lg:opacity-0 lg:max-w-0 opacity-100 max-w-[200px]'}`}>{t('common.newChat')}</span>
          </button>
        </div>

        {/* Strategy Nexus */}
        <div className={`${isSidebarOpen ? 'px-2' : 'lg:px-2 px-2'}`}>
          <button
            onClick={() => { setShowStrategyNexus(true); setShowDailyReport(false); setSessionId(null); setMessages([]); }}
            className={`w-full flex items-center gap-3 py-3 rounded-lg transition-colors ${isSidebarOpen ? 'px-4' : 'lg:justify-center lg:px-0 px-4'} ${showStrategyNexus ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-800/50 hover:text-white'}`}
            title={t('sidebar.strategyNexus')}
          >
            <Activity className={`w-5 h-5 flex-shrink-0 ${showStrategyNexus ? 'text-indigo-400' : ''}`} />
            <span className={`font-medium whitespace-nowrap overflow-hidden transition-all duration-300 ${isSidebarOpen ? 'opacity-100 max-w-[200px]' : 'lg:opacity-0 lg:max-w-0 opacity-100 max-w-[200px]'}`}>{t('sidebar.strategyNexus')}</span>
          </button>
        </div>

        {/* Daily Report */}
        <div className={`${isSidebarOpen ? 'px-2' : 'lg:px-2 px-2'}`}>
          <button
            onClick={() => { setShowDailyReport(true); setShowStrategyNexus(false); setSessionId(null); setMessages([]); }}
            className={`w-full flex items-center gap-3 py-3 rounded-lg transition-colors ${isSidebarOpen ? 'px-4' : 'lg:justify-center lg:px-0 px-4'} ${showDailyReport ? 'bg-slate-800 text-white' : 'text-slate-300 hover:bg-slate-800/50 hover:text-white'}`}
            title={t('sidebar.dailyReport')}
          >
            <Newspaper className={`w-5 h-5 flex-shrink-0 ${showDailyReport ? 'text-indigo-400' : ''}`} />
            <span className={`font-medium whitespace-nowrap overflow-hidden transition-all duration-300 ${isSidebarOpen ? 'opacity-100 max-w-[200px]' : 'lg:opacity-0 lg:max-w-0 opacity-100 max-w-[200px]'}`}>{t('sidebar.dailyReport')}</span>
          </button>
        </div>

        {/* History List */}
        <div className={`flex-1 flex flex-col px-2 py-2 ${!isSidebarOpen && 'lg:overflow-visible'} ${isSidebarOpen && 'overflow-y-auto'}`}>
          <div className={`border-t border-slate-800 my-2 ${!isSidebarOpen && 'lg:mx-1'}`}></div>

          {/* 展开状态 - 显示完整列表 */}
          {isSidebarOpen ? (
            <>
              <div className="px-4 pb-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                {t('sidebar.recentChats')}
              </div>
              <div className="space-y-1 flex-1 overflow-y-auto">
                {sessions.map((session) => (
                  <div
                    key={session.session_id}
                    className={`relative w-full text-left px-4 py-3 rounded-lg transition-colors flex items-center gap-3 group
                          ${sessionId === session.session_id ? 'bg-slate-800 text-white' : 'hover:bg-slate-800/50 text-slate-300'}
                        `}
                  >
                    <button
                      onClick={() => loadSession(session.session_id)}
                      className="flex items-center gap-3 flex-1 min-w-0"
                    >
                      <MessageSquare className={`w-4 h-4 flex-shrink-0 ${sessionId === session.session_id ? 'text-indigo-400' : 'text-slate-500 group-hover:text-indigo-400'}`} />
                      <span className="truncate text-sm">{session.title || t('common.untitledChat')}</span>
                    </button>
                    {/* 3-dot menu button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSessionMenuOpen(sessionMenuOpen === session.session_id ? null : session.session_id);
                      }}
                      className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-slate-700 transition-all"
                    >
                      <MoreVertical className="w-4 h-4 text-slate-400" />
                    </button>
                    {/* Session menu dropdown */}
                    {sessionMenuOpen === session.session_id && (
                      <div data-session-menu className="absolute right-2 top-full mt-1 z-50 bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1 min-w-[120px]">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setRenameInput(session.title || '');
                            setRenameDialogOpen(session);
                            setSessionMenuOpen(null);
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-300 hover:bg-slate-700"
                        >
                          <Edit3 className="w-4 h-4" />
                          {t('sidebar.rename')}
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteConfirmOpen(session);
                            setSessionMenuOpen(null);
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-slate-700"
                        >
                          <Trash2 className="w-4 h-4" />
                          {t('auth.delete')}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
                {sessions.length === 0 && (
                  <div className="px-4 py-4 text-center text-sm text-slate-600">
                    {t('auth.noHistoryYet')}
                  </div>
                )}
              </div>
            </>
          ) : (
            /* 折叠状态 */
            <>
              {/* 历史记录图标 - 放在顶部 */}
              <div className="hidden lg:block relative group">
                <button
                  className="w-full flex justify-center py-3 rounded-lg text-slate-300 hover:bg-slate-800/50 hover:text-white transition-colors"
                  title={t('common.history')}
                >
                  <History className="w-5 h-5" />
                </button>
                {/* Hover 弹出列表 */}
                {sessions.length > 0 && (
                  <div className="absolute left-full top-0 ml-2 w-64 bg-slate-800 rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 max-h-80 overflow-y-auto">
                    <div className="px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-700">
                      Recent
                    </div>
                    {sessions.map((session) => (
                      <button
                        key={session.session_id}
                        onClick={() => loadSession(session.session_id)}
                        className={`w-full text-left px-4 py-2.5 transition-colors flex items-center gap-3
                              ${sessionId === session.session_id ? 'bg-slate-700 text-white' : 'hover:bg-slate-700 text-slate-300'}
                            `}
                      >
                        <MessageSquare className={`w-4 h-4 flex-shrink-0 ${sessionId === session.session_id ? 'text-indigo-400' : 'text-slate-500'}`} />
                        <span className="truncate text-sm">{session.title || t('common.untitledChat')}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* 空白点击区域 - 占满剩余空间 */}
              <div
                className="hidden lg:flex flex-1 cursor-ew-resize items-center justify-center"
                onClick={() => setIsSidebarOpen(true)}
              />
            </>
          )}

          {/* 移动端保持原样 */}
          <div className="lg:hidden space-y-1">
            {!isSidebarOpen && sessions.map((session) => (
              <button
                key={session.session_id}
                onClick={() => loadSession(session.session_id)}
                className={`w-full text-left px-4 py-3 rounded-lg transition-colors flex items-center gap-3 group
                      ${sessionId === session.session_id ? 'bg-slate-800 text-white' : 'hover:bg-slate-800/50 text-slate-300'}
                    `}
              >
                <MessageSquare className={`w-4 h-4 flex-shrink-0 ${sessionId === session.session_id ? 'text-indigo-400' : 'text-slate-500 group-hover:text-indigo-400'}`} />
                <span className="truncate text-sm">{session.title || t('common.untitledChat')}</span>
              </button>
            ))}
          </div>
        </div>

        {/* User Profile */}
        <div className={`p-3 border-t border-slate-800 bg-slate-900/50 ${!isSidebarOpen && 'lg:flex lg:justify-center'}`}>
          {user ? (
            // Logged in user
            <div className="relative" ref={userMenuRef}>
              <div
                className={`flex items-center gap-3 rounded-lg transition-colors ${isSidebarOpen ? 'w-full px-2 py-1' : 'lg:p-2 w-full px-2 py-1'}`}
              >
                {/* Avatar - clickable */}
                <div
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                >
                  {(user.user_metadata?.picture || user.user_metadata?.avatar_url) ? (
                    <img
                      src={user.user_metadata.picture || user.user_metadata.avatar_url}
                      alt="avatar"
                      className="w-8 h-8 rounded-full flex-shrink-0 object-cover"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-violet-500 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                      {user.user_metadata?.full_name?.[0]?.toUpperCase() || user.user_metadata?.name?.[0]?.toUpperCase() || user.email?.[0]?.toUpperCase() || 'W'}
                    </div>
                  )}
                </div>
                {/* Credits badge - capsule style */}
                <div className={`flex items-center gap-2 overflow-hidden transition-all duration-300 ${isSidebarOpen ? 'opacity-100 max-w-[200px]' : 'lg:opacity-0 lg:max-w-0 opacity-100 max-w-[200px]'}`}>
                  {/* Check-in button */}
                  <button
                    onClick={async (e) => {
                      e.stopPropagation();
                      if (!userId) return;
                      try {
                        const res = await fetch(`${BASE_URL}/api/credits/${userId}/checkin`, { method: 'POST' });
                        const data = await res.json();
                        if (data.success) {
                          setCredits(data.current_credits);
                          setCheckedInToday(true);
                        }
                        // Show toast
                        setToast({ message: data.message, type: data.success ? 'success' : 'info' });
                        setTimeout(() => setToast(null), 3000);
                      } catch (err) {
                        console.error('Check-in error:', err);
                        setToast({ message: t('common.error'), type: 'error' });
                        setTimeout(() => setToast(null), 3000);
                      }
                    }}
                    disabled={checkedInToday}
                    className={`px-2 py-1 rounded-full text-xs font-medium transition-colors ${checkedInToday
                      ? 'bg-slate-700/50 text-slate-500 cursor-not-allowed'
                      : 'bg-green-500/20 text-green-400 hover:bg-green-500/30 border border-green-500/30'
                      }`}
                    title={checkedInToday ? t('credits.checkedIn') : t('credits.checkIn')}
                  >
                    {checkedInToday ? '✓' : '🎁'}
                  </button>
                  {/* Credits display */}
                  <div className="flex items-center gap-1.5 px-3 py-1 bg-indigo-500/20 rounded-full border border-indigo-500/30">
                    <Zap className="w-3.5 h-3.5 text-indigo-400" />
                    <span className="text-sm font-semibold text-indigo-300">{credits ?? '--'}</span>
                  </div>
                </div>
              </div>

              {/* User Dropdown Menu - positioned outside sidebar when collapsed */}
              {showUserMenu && (
                <div className={`mb-2 bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden z-[100] ${isSidebarOpen
                    ? 'absolute bottom-full left-0 right-0'
                    : 'fixed bottom-20 left-2 lg:left-16 w-56'
                  }`}>
                  {/* User info header */}
                  <div className="px-4 py-3 border-b border-slate-700">
                    <div className="flex items-center gap-3">
                      {/* Avatar in dropdown */}
                      {(user.user_metadata?.picture || user.user_metadata?.avatar_url) ? (
                        <img
                          src={user.user_metadata.picture || user.user_metadata.avatar_url}
                          alt="avatar"
                          className="w-10 h-10 rounded-full flex-shrink-0 object-cover"
                          referrerPolicy="no-referrer"
                        />
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-500 to-violet-500 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                          {user.user_metadata?.full_name?.[0]?.toUpperCase() || user.user_metadata?.name?.[0]?.toUpperCase() || user.email?.[0]?.toUpperCase() || 'W'}
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        {/* Name - email prefix for email users, "Wallet" for wallet users */}
                        <div className="text-sm font-medium text-white truncate">
                          {user.user_metadata?.full_name ||
                            user.user_metadata?.name ||
                            (user.email && !user.email.includes('@wallet.local') ? user.email.split('@')[0] : 'Wallet')}
                        </div>
                        {/* Email or wallet address */}
                        <div className="text-xs text-slate-400 truncate">
                          {user.email && !user.email.includes('@wallet.local')
                            ? user.email
                            : user.user_metadata?.wallet_address
                              ? `${user.user_metadata.wallet_address.slice(0, 6)}***${user.user_metadata.wallet_address.slice(-4)}`
                              : user.email?.replace('@wallet.local', '').slice(0, 6) + '***' + user.email?.replace('@wallet.local', '').slice(-4)
                          }
                        </div>
                      </div>
                    </div>
                  </div>
                  {/* Settings button */}
                  <button
                    onClick={() => {
                      setShowSettingsModal(true);
                      setShowUserMenu(false);
                    }}
                    className="w-full flex items-center gap-2 px-4 py-3 text-sm text-slate-300 hover:bg-slate-700 transition-colors"
                  >
                    <Settings className="w-4 h-4" />
                    <span>{t('auth.settings')}</span>
                  </button>
                  {/* Sign out button */}
                  <button
                    onClick={async () => {
                      await signOut();
                      setShowUserMenu(false);
                      startNewChat();
                    }}
                    className="w-full flex items-center gap-2 px-4 py-3 text-sm text-red-400 hover:bg-slate-700 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>{t('auth.signOut')}</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            // 未登录
            <button
              onClick={() => setShowAuthModal(true)}
              className={`flex items-center justify-center gap-2 py-3 bg-[#131722] hover:bg-slate-700 text-white rounded-lg transition-colors ${isSidebarOpen ? 'w-full px-4' : 'lg:p-2 w-full px-4'}`}
              title={t('common.signInSignUp')}
            >
              <LogIn className="w-4 h-4 flex-shrink-0" />
              <span className={`whitespace-nowrap overflow-hidden transition-all duration-300 ${isSidebarOpen ? 'opacity-100 max-w-[200px]' : 'lg:opacity-0 lg:max-w-0 opacity-100 max-w-[200px]'}`}>{t('auth.signIn')}</span>
            </button>
          )}
        </div>
      </aside>

      {/* Main Content Area - includes chat and workspace */}
      <div className="flex-1 flex h-full min-w-0 overflow-hidden">
        {/* Daily Report */}
        {showDailyReport ? (
          <DailyReport onBack={() => setShowDailyReport(false)} />
        ) : showStrategyNexus ? (
          <StrategyNexus userId={userId} onBack={() => setShowStrategyNexus(false)} />
        ) : (
          /* Chat Section */
          <main className={`flex flex-col h-full relative bg-black transition-all duration-300 overflow-hidden ${workspaceOpen ? 'w-1/3 min-w-[400px]' : 'flex-1'}`}>

            {/* Header with TrendingBar */}
            <header className="bg-black sticky top-0 z-10 flex items-center">
              {/* Mobile menu button */}
              <button
                onClick={() => setShowMobileSidebar(!showMobileSidebar)}
                className="lg:hidden p-2 ml-2 text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded-lg transition-colors flex-shrink-0"
              >
                <History className="w-5 h-5" />
              </button>

              {/* TrendingBar */}
              <div className="flex-1 min-w-0">
                <TrendingBar
                  tokens={trendingTokens}
                  loading={trendingLoading}
                  onTokenClick={(symbol) => {
                    setInput(`分析 ${symbol} 的走势`);
                    inputRef.current?.focus();
                  }}
                />
              </div>
            </header>

            {/* View Switcher */}
            {messages.length === 0 ? (
              // --- Home View (Manus Style) - scrollable ---
              <div className="flex-1 overflow-x-hidden overflow-y-auto">
                <div className="min-h-full flex flex-col items-center py-16 md:py-20 px-4">
                  {/* Title and Input - centered 768px width */}
                  <div className="w-full space-y-6 text-center mb-8" style={{ maxWidth: '768px' }}>

                    <SuggestedQuestion
                      userId={userId}
                      onFillInput={(text) => setInput(text)}
                    />

                    <div className="relative group">
                      <div className="relative bg-[#131722] border border-white/10 rounded-2xl flex flex-col p-5 shadow-xl">
                        {/* Text input area */}
                        <textarea
                          ref={inputRef}
                          value={input}
                          onChange={(e) => {
                            setInput(e.target.value);
                            e.target.style.height = '48px';
                            e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                              e.preventDefault();
                              handleSend();
                            }
                          }}
                          placeholder={selectedAgent === 'trader' ? t('agentMode.traderPlaceholder') : t('agentMode.analystPlaceholder')}
                          className="w-full bg-transparent border-none outline-none focus:ring-0 focus:outline-none resize-none text-slate-100 placeholder:text-slate-500 text-lg leading-relaxed font-light"
                          rows={1}
                          style={{ minHeight: '48px', maxHeight: '120px' }}
                        />

                        {/* Toolbar - no divider, just spacing */}
                        <div className="flex items-center justify-between mt-4">
                          {/* Agent Mode Tabs - inline toggle like the reference image */}
                          {messages.length === 0 && (
                            <div className="flex items-center bg-slate-800 rounded-lg p-1">
                              <button
                                onClick={() => setSelectedAgent('analyst')}
                                className={`px-3 py-1 text-sm font-medium rounded-md transition-all ${selectedAgent === 'analyst'
                                  ? 'bg-slate-700 text-white'
                                  : 'text-slate-400 hover:text-white'
                                  }`}
                              >
                                {t('agentMode.analyst')}
                              </button>
                              <button
                                onClick={() => setSelectedAgent('trader')}
                                className={`px-3 py-1 text-sm font-medium rounded-md transition-all ${selectedAgent === 'trader'
                                  ? 'bg-slate-700 text-white'
                                  : 'text-slate-400 hover:text-white'
                                  }`}
                              >
                                {t('agentMode.trader')}
                              </button>
                            </div>
                          )}
                          {messages.length > 0 && <div />}

                          {/* Send button - solid purple */}
                          <button
                            onClick={() => handleSend()}
                            disabled={!input.trim()}
                            className="w-8 h-8 rounded-lg bg-indigo-500 hover:bg-indigo-400 text-white disabled:opacity-30 disabled:bg-slate-600 flex items-center justify-center transition-all shadow-lg shadow-indigo-500/20"
                          >
                            <ArrowUp className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Dashboard Components - Full Width */}
                  <div className="w-full px-8 lg:px-20 overflow-hidden">
                    <div className="flex flex-col gap-4 min-w-0">

                      {/* Row 1: Quick Prompts (50%) + Latest News (50%) */}
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 min-w-0">
                        {/* Top Left: Trending Prompts - Pills with rotation */}
                        {(() => {
                          // Static prompts from translations
                          const staticPrompts = [
                            { key: 'marketAnalysis', text: t('home.quickPrompts.marketAnalysis') },
                            { key: 'investmentStrategies', text: t('home.quickPrompts.investmentStrategies') },
                            { key: 'marketForecast', text: t('home.quickPrompts.marketForecast') },
                            { key: 'investmentOpportunities', text: t('home.quickPrompts.investmentOpportunities') },
                            { key: 'topGainers', text: t('home.quickPrompts.topGainers') },
                            { key: 'defiYields', text: t('home.quickPrompts.defiYields') },
                            { key: 'whale', text: t('home.quickPrompts.whale') },
                            { key: 'meme', text: t('home.quickPrompts.meme') },
                            { key: 'airdrop', text: t('home.quickPrompts.airdrop') },
                            { key: 'layer2', text: t('home.quickPrompts.layer2') },
                            { key: 'altseason', text: t('home.quickPrompts.altseason') },
                            { key: 'macro', text: t('home.quickPrompts.macro') }
                          ];
                          return (
                            <QuickPromptsPills
                              staticPrompts={staticPrompts}
                              onSelectPrompt={(text) => setInput(text)}
                            />
                          );
                        })()}

                        {/* Top Right: Latest News */}
                        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden">
                          {dashboardLoading ? (
                            /* 骨架屏 - 被容器 overflow-hidden 限制 */
                            <>
                              <div className="flex items-center gap-2 mb-3">
                                <div className="bg-slate-700/50 animate-pulse rounded-full w-4 h-4" />
                                <div className="bg-slate-700/50 animate-pulse rounded w-20 h-4" />
                              </div>
                              <div className="flex flex-col justify-between h-[calc(100%-32px)]">
                                {[...Array(5)].map((_, i) => (
                                  <div key={i} className="flex items-start gap-2 px-2 py-1">
                                    <div className="bg-slate-700/50 animate-pulse rounded w-4 h-4 flex-shrink-0 mt-0.5" />
                                    <div className="flex-1">
                                      <div className="bg-slate-700/50 animate-pulse rounded h-4 w-3/4" />
                                      <div className="bg-slate-700/50 animate-pulse rounded h-3 w-1/2 mt-1" />
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </>
                          ) : (
                            /* 真实内容 */
                            <>
                              <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                                <Newspaper className="w-4 h-4 text-blue-400" />
                                {t('home.latestNews')}
                              </h3>
                              <div className="flex flex-col justify-between h-[calc(100%-32px)]">
                                {dashboardNews.length > 0 ? dashboardNews.slice(0, 5).map((news, i) => {
                                  const isZh = i18n.language?.startsWith('zh');
                                  const displayTitle = isZh ? (news.title_zh || news.title || news.title_en) : (news.title_en || news.title);
                                  const displaySummary = isZh ? (news.summary_zh || '') : (news.summary_en || '');
                                  return (
                                    <button
                                      key={i}
                                      onClick={() => setInput(`${t('dashboard.analyzeNews', 'Analyze news')}: '${displayTitle}'`)}
                                      className="w-full flex items-start gap-2 px-2 py-1 hover:bg-slate-800 rounded-lg transition-colors text-left"
                                    >
                                      <span className="text-xs text-slate-500 mt-0.5 flex-shrink-0">{i + 1}.</span>
                                      <div className="flex-1">
                                        <span className="text-sm text-slate-300 line-clamp-1">{displayTitle}</span>
                                        {displaySummary && (
                                          <span className="text-xs text-slate-500 line-clamp-1 block mt-0.5">{displaySummary}</span>
                                        )}
                                      </div>
                                    </button>
                                  )
                                }) : (() => {
                                  const DEFAULT_NEWS = [
                                    { title_en: "Bitcoin holds steady as market awaits Fed decision", title_zh: "比特币保持稳定，市场等待美联储决议" },
                                    { title_en: "Ethereum Layer 2 solutions see record TVL growth", title_zh: "以太坊二层解决方案TVL创历史新高" },
                                    { title_en: "Institutional crypto adoption accelerates in Asia", title_zh: "亚洲机构加密货币采用加速" },
                                    { title_en: "DeFi protocols show renewed growth momentum", title_zh: "DeFi协议增长势头强劲" },
                                    { title_en: "NFT market sees signs of recovery in Q4", title_zh: "NFT市场第四季度复苏迹象显现" }
                                  ];
                                  const isZh = i18n.language?.startsWith('zh');
                                  return DEFAULT_NEWS.map((news, i) => {
                                    const displayTitle = isZh ? news.title_zh : news.title_en;
                                    return (
                                      <button
                                        key={i}
                                        onClick={() => setInput(`${t('dashboard.analyzeNews', 'Analyze news')}: '${displayTitle}'`)}
                                        className="w-full flex items-start gap-2 px-2 py-1.5 hover:bg-slate-800 rounded-lg transition-colors text-left"
                                      >
                                        <span className="text-xs text-slate-500">{i + 1}.</span>
                                        <span className="text-sm text-slate-300">{displayTitle}</span>
                                      </button>
                                    );
                                  });
                                })()}
                              </div>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Row 2: Popular Tokens (50%) + Key Indicators (50%) */}
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 min-w-0">
                        {/* Bottom Left: Popular Tokens */}
                        {/* Bottom Left: Popular Tokens */}
                        {dashboardLoading ? (
                          <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden">
                            {/* 骨架屏 */}
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-2">
                                <div className="bg-slate-700/50 animate-pulse rounded-full w-4 h-4" />
                                <div className="bg-slate-700/50 animate-pulse rounded w-20 h-4" />
                              </div>
                              <div className="flex bg-slate-800/50 rounded-lg p-0.5 gap-1">
                                <div className="bg-slate-700/50 animate-pulse rounded-md w-12 h-6" />
                                <div className="bg-slate-700/50 animate-pulse rounded-md w-14 h-6" />
                              </div>
                            </div>
                            <div className="grid grid-cols-4 px-2 pb-1 border-b border-slate-800/50 mb-1">
                              <div className="bg-slate-700/50 animate-pulse rounded w-10 h-3" />
                              <div className="bg-slate-700/50 animate-pulse rounded w-10 h-3 ml-auto" />
                              <div className="bg-slate-700/50 animate-pulse rounded w-10 h-3 ml-auto" />
                              <div />
                            </div>
                            <div className="flex-1 flex flex-col justify-between">
                              {[...Array(6)].map((_, i) => (
                                <div key={i} className="grid grid-cols-4 items-center px-2 py-1.5">
                                  <div className="bg-slate-700/50 animate-pulse rounded w-14 h-4" />
                                  <div className="bg-slate-700/50 animate-pulse rounded w-16 h-4 ml-auto" />
                                  <div className="bg-slate-700/50 animate-pulse rounded w-12 h-4 ml-auto" />
                                  <div className="bg-slate-700/50 animate-pulse rounded-full w-4 h-4 ml-auto" />
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <PopularTokens
                            tokens={dashboardTokens}
                            onAnalyzeToken={(prompt) => setInput(prompt)}
                          />
                        )}

                        {/* Bottom Right: Key Indicators + Fear & Greed */}
                        <div className="bg-[#131722] rounded-xl p-5 border border-slate-800 h-[330px] overflow-hidden">
                          {dashboardLoading ? (
                            /* 骨架屏 */
                            <>
                              <div className="flex items-center gap-2 mb-3">
                                <div className="bg-slate-700/50 animate-pulse rounded-full w-4 h-4" />
                                <div className="bg-slate-700/50 animate-pulse rounded w-24 h-4" />
                              </div>
                              <div className="w-full flex items-center justify-between p-3 bg-slate-800/50 rounded-lg mb-3">
                                <div className="flex items-center gap-2">
                                  <div className="bg-slate-700/50 animate-pulse rounded-full w-4 h-4" />
                                  <div className="bg-slate-700/50 animate-pulse rounded w-20 h-3" />
                                </div>
                                <div className="flex items-center gap-2">
                                  <div className="bg-slate-700/50 animate-pulse rounded w-8 h-5" />
                                  <div className="bg-slate-700/50 animate-pulse rounded w-12 h-3" />
                                </div>
                              </div>
                              <div className="grid grid-cols-2 gap-2">
                                {[...Array(6)].map((_, i) => (
                                  <div key={i} className="flex flex-col p-2.5 bg-slate-800/50 rounded-lg">
                                    <div className="bg-slate-700/50 animate-pulse rounded w-16 h-3 mb-1" />
                                    <div className="bg-slate-700/50 animate-pulse rounded w-12 h-4" />
                                  </div>
                                ))}
                              </div>
                            </>
                          ) : (
                            /* 真实内容 */
                            <>
                              <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                                <BarChart2 className="w-4 h-4 text-cyan-400" />
                                {t('home.keyIndicators.title')}
                              </h3>

                              {/* Fear & Greed at top */}
                              <button
                                onClick={() => {
                                  const translatedClassification = t(`home.keyIndicators.classifications.${dashboardFearGreed.classification}`, dashboardFearGreed.classification);
                                  setInput(`${t('dashboard.analyzeFearGreed', 'Analyze Fear & Greed Index')}: ${dashboardFearGreed.value} (${translatedClassification})`);
                                }}
                                className="w-full flex items-center justify-between p-3 bg-slate-800/50 hover:bg-slate-700 rounded-lg mb-3 transition-colors"
                              >
                                <div className="flex items-center gap-2">
                                  <Activity className="w-4 h-4 text-yellow-400" />
                                  <span className="text-xs text-slate-400">{t('home.keyIndicators.fearGreed')}</span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className={`text-lg font-bold ${dashboardFearGreed.value <= 25 ? 'text-red-400' :
                                    dashboardFearGreed.value <= 45 ? 'text-orange-400' :
                                      dashboardFearGreed.value <= 55 ? 'text-yellow-400' :
                                        dashboardFearGreed.value <= 75 ? 'text-lime-400' : 'text-green-400'
                                    }`}>{dashboardFearGreed.value}</span>
                                  <span className="text-xs text-slate-500">{t(`home.keyIndicators.classifications.${dashboardFearGreed.classification}`, dashboardFearGreed.classification)}</span>
                                </div>
                              </button>

                              {/* Other indicators */}
                              <div className="grid grid-cols-2 gap-2">
                                {dashboardIndicators.map((indicator, i) => {
                                  const nameKeyMap = {
                                    'Total Market Cap': 'totalMarketCap',
                                    'Bitcoin Market Cap': 'bitcoinMarketCap',
                                    'Bitcoin Dominance': 'bitcoinDominance',
                                    'ETH/BTC Ratio': 'ethBtcRatio',
                                    'Ethereum Gas': 'ethereumGas',
                                    'DeFi TVL': 'defiTvl'
                                  };
                                  const translatedName = nameKeyMap[indicator.name]
                                    ? t(`home.keyIndicators.${nameKeyMap[indicator.name]}`)
                                    : indicator.name;

                                  return (
                                    <button
                                      key={i}
                                      onClick={() => setInput(`${t('dashboard.analyzeIndicator', 'Analyze')}: ${translatedName} ${indicator.value}`)}
                                      className="flex flex-col p-2.5 bg-slate-800/50 hover:bg-slate-700 rounded-lg transition-colors text-left"
                                    >
                                      <span className="text-xs text-slate-500 truncate">{translatedName}</span>
                                      <span className="text-sm font-medium text-white mt-0.5">{indicator.value}</span>
                                    </button>
                                  );
                                })}
                              </div>
                            </>
                          )}
                        </div>
                      </div>

                    </div>
                  </div>
                </div>
              </div>
            ) : (
              // --- Chat View ---
              <>
                <div className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8 scroll-smooth bg-black">
                  <div className="max-w-3xl mx-auto space-y-6">
                    {messages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}
                      >
                        {msg.role === 'assistant' && (
                          <div className="w-8 h-8 rounded-lg bg-[#131722] flex items-center justify-center flex-shrink-0 mt-1">
                            <Sparkles className="w-4 h-4 text-indigo-500" />
                          </div>
                        )}

                        {msg.role === 'user' ? (
                          <div className="relative max-w-[85%] md:max-w-[75%] rounded-2xl px-5 py-3.5 bg-[#131722] text-white">
                            <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                          </div>
                        ) : (
                          <MessageContent content={msg.content} toolStartTimes={toolStartTimes} messageIndex={idx} />
                        )}
                      </div>
                    ))}

                    {isLoading && messages[messages.length - 1].role === 'user' && (
                      <div className="flex gap-4 justify-start animate-in fade-in duration-300">
                        <div className="w-8 h-8 rounded-lg bg-[#131722] flex items-center justify-center flex-shrink-0 mt-1">
                          <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                        </div>
                        <div className="bg-[#131722] rounded-2xl px-5 py-4 flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                          <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                          <span className="w-1.5 h-1.5 bg-purple-400 rounded-full animate-bounce"></span>
                        </div>
                      </div>
                    )}

                    {/* Thinking indicator - shows when agent is processing between tool calls */}
                    {isLoading && isThinking && messages[messages.length - 1]?.role === 'assistant' && (
                      <div className="flex gap-4 justify-start animate-in fade-in duration-200 ml-12">
                        <div className="bg-[#131722] rounded-xl px-4 py-2.5 flex items-center gap-2">
                          <div className="relative">
                            <Sparkles className="w-4 h-4 text-purple-400" />
                            <div className="absolute inset-0 animate-ping">
                              <Sparkles className="w-4 h-4 text-purple-400 opacity-50" />
                            </div>
                          </div>
                          <span className="text-sm text-slate-300 font-medium">Alpha is analyzing...</span>
                          <div className="flex gap-0.5 ml-1">
                            <span className="w-1 h-1 bg-purple-400 rounded-full animate-pulse [animation-delay:-0.3s]"></span>
                            <span className="w-1 h-1 bg-purple-400 rounded-full animate-pulse [animation-delay:-0.15s]"></span>
                            <span className="w-1 h-1 bg-purple-400 rounded-full animate-pulse"></span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Coin Button Bar - appears after analysis completes */}
                    {!isLoading && detectedCoins.length > 0 && (
                      <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 ml-12">
                        <CoinButtonBar coins={detectedCoins} onCoinClick={handleCoinClick} />
                      </div>
                    )}

                    <div ref={messagesEndRef} className="h-4" />
                  </div>
                </div>

                {/* Chat Input Area */}
                <div className="p-4 bg-black">
                  <div className="max-w-3xl mx-auto relative">
                    <div className="relative flex items-end gap-2 bg-[#131722] rounded-xl">
                      <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => {
                          setInput(e.target.value);
                          // Auto-resize: reset height then set to scrollHeight, max 5 lines (~120px)
                          e.target.style.height = '48px';
                          e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                        }}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault();
                            if (!isLoading) handleSend();
                          }
                        }}
                        placeholder="Message Crypto Analyst..."
                        className="w-full p-3.5 bg-transparent border-none focus:ring-0 resize-none text-slate-100 placeholder:text-slate-500 text-sm leading-relaxed overflow-y-auto"
                        rows={1}
                        style={{ minHeight: '48px', maxHeight: '120px' }}
                        disabled={isLoading}
                      />

                      <div className="pb-1.5 pr-1.5">
                        {isLoading ? (
                          <button
                            onClick={handleStop}
                            className="p-2 bg-slate-600 text-slate-300 hover:bg-slate-500 rounded-lg transition-colors"
                          >
                            <StopCircle className="w-4 h-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => handleSend()}
                            disabled={!input.trim()}
                            className="p-2 bg-[#131722] hover:bg-slate-700 text-white disabled:opacity-30 rounded-lg transition-all duration-200"
                          >
                            <Send className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="text-center mt-2">
                      <p className="text-[10px] text-slate-400">
                        AI can make mistakes. Please verify important information.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}

          </main>
        )}

        {/* Workspace Panel - TradingView Charts */}
        {workspaceOpen && activeChart && (
          <div className="w-2/3 h-full border-l border-slate-200 bg-white animate-in slide-in-from-right duration-300">
            <TradingViewWidget
              symbol={activeChart.symbol}
              onClose={handleCloseWorkspace}
            />
          </div>
        )}
      </div>
      {/* Rename Dialog */}
      {renameDialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onKeyDown={(e) => { if (e.key === 'Escape') { setRenameDialogOpen(null); setRenameInput(''); } }}
        >
          <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm cursor-pointer" onClick={() => { setRenameDialogOpen(null); setRenameInput(''); }} />
          <div className="relative bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700">
            <h3 className="text-lg font-semibold text-white mb-4">{t('sidebar.renameChat')}</h3>
            <input
              type="text"
              value={renameInput}
              onChange={(e) => setRenameInput(e.target.value)}
              placeholder={t('sidebar.enterNewName')}
              className="w-full px-4 py-3 bg-slate-700 rounded-lg text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-4"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleRenameSession(renameDialogOpen.session_id);
                if (e.key === 'Escape') { setRenameDialogOpen(null); setRenameInput(''); }
              }}
            />
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setRenameDialogOpen(null); setRenameInput(''); }}
                className="px-4 py-2 rounded-lg text-slate-300 hover:bg-slate-700 transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => handleRenameSession(renameDialogOpen.session_id)}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
              >
                {t('sidebar.rename')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deleteConfirmOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onKeyDown={(e) => { if (e.key === 'Escape') setDeleteConfirmOpen(null); }}
          tabIndex={-1}
        >
          <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm cursor-pointer" onClick={() => setDeleteConfirmOpen(null)} />
          <div className="relative bg-slate-800 rounded-xl p-6 w-full max-w-md shadow-2xl border border-slate-700">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-500/20 rounded-full">
                <AlertTriangle className="w-6 h-6 text-red-400" />
              </div>
              <h3 className="text-lg font-semibold text-white">{t('sidebar.deleteChat')}</h3>
            </div>
            <p className="text-slate-300 mb-6">
              {t('sidebar.deleteChatConfirm')}
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteConfirmOpen(null)}
                className="px-4 py-2 rounded-lg text-slate-300 hover:bg-slate-700 transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => handleDeleteSession(deleteConfirmOpen.session_id)}
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-medium transition-colors"
              >
                {t('common.delete')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Auth Modal */}
      <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />

      {/* Settings Modal */}
      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        user={{
          displayName: user?.user_metadata?.full_name || user?.user_metadata?.name || (user?.email?.split('@')[0]),
          email: user?.email,
          avatarUrl: user?.user_metadata?.picture || user?.user_metadata?.avatar_url
        }}
        credits={credits}
        onSignOut={async () => {
          await signOut();
          startNewChat();
        }}
        creditsHistory={creditsHistory}
      />
    </div>
  );
}

// Wrap AppContent with AuthProvider
function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  useEffect(() => {
    const handlePopState = () => setCurrentPath(window.location.pathname);
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigateHome = () => {
    window.history.pushState({}, '', '/');
    setCurrentPath('/');
  };

  // Route based on URL path
  if (currentPath === '/home') {
    return <HomePage />;
  }
  if (currentPath === '/privacy') {
    return <PrivacyPolicy onBack={navigateHome} />;
  }
  if (currentPath === '/terms') {
    return <TermsOfService onBack={navigateHome} />;
  }

  return (
    <AuthProvider>
      <AuthWrapper />
    </AuthProvider>
  );
}

// Wrapper component that decides between LandingPage and AppContent
function AuthWrapper() {
  const { user, loading: authLoading } = useAuth();
  const { i18n } = useTranslation();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [showLoader, setShowLoader] = useState(false);
  const [initialDataLoaded, setInitialDataLoaded] = useState(false);

  // 追踪是否已经显示过加载动画（刷新页面会重置，切换标签页不会）
  const hasShownLoaderRef = React.useRef(false);

  const handleLanguageChange = () => {
    i18n.changeLanguage(i18n.language === 'en' ? 'zh' : 'en');
  };

  const handleLogin = (mode) => {
    setAuthMode(mode);
    setShowAuthModal(true);
  };

  // 只在首次加载时显示加载动画，切换标签页回来不再显示
  useEffect(() => {
    if (user && !authLoading && !hasShownLoaderRef.current) {
      // 标记已显示过加载动画
      hasShownLoaderRef.current = true;

      setShowLoader(true);
      setInitialDataLoaded(false);

      // 加载首页所需的数据
      const loadInitialData = async () => {
        const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

        try {
          // 并行加载用户数据和 dashboard 数据
          await Promise.all([
            // 用户积分
            fetch(`${BASE_URL}/api/credits/${user.id}`).then(r => r.json()).catch(() => ({})),
            // 签到状态
            fetch(`${BASE_URL}/api/credits/${user.id}/checkin-status`).then(r => r.json()).catch(() => ({})),
            // Dashboard 数据
            fetch(`${BASE_URL}/api/dashboard/tokens`).then(r => r.json()).catch(() => ({})),
            fetch(`${BASE_URL}/api/dashboard/fear-greed`).then(r => r.json()).catch(() => ({})),
          ]);
        } catch (e) {
          console.error('Initial data load error:', e);
        }

        setInitialDataLoaded(true);
      };

      loadInitialData();
    }
  }, [user, authLoading]);

  // 加载动画完成后隐藏
  const handleLoaderComplete = () => {
    setShowLoader(false);
  };

  // Auth 状态检查中 - 显示简单的 loading
  if (authLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full" />
      </div>
    );
  }

  // Show LandingPage for unauthenticated users
  if (!user) {
    return (
      <>
        <LandingPage
          onLogin={handleLogin}
          onLanguageChange={handleLanguageChange}
          currentLanguage={i18n.language}
        />
        <AuthModal
          isOpen={showAuthModal}
          onClose={() => setShowAuthModal(false)}
          initialMode={authMode}
        />
      </>
    );
  }

  // 已登录用户 - 显示全屏加载动画直到数据加载完成
  if (showLoader) {
    return (
      <TerminalLoader
        fullScreen={true}
        isReady={initialDataLoaded}
        onComplete={handleLoaderComplete}
      />
    );
  }

  // Show main app for authenticated users
  return <AppContent />;
}

export default App;
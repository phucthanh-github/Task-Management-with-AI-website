import { useState, useEffect, useRef } from 'react';
import { 
  CheckCircle, 
  Circle,
  Trash2, 
  Edit3,
  Plus, 
  Send, 
  LogOut, 
  Bot, 
  User, 
  AlertCircle, 
  Clock, 
  RefreshCw,
  X,
  MessageSquare,
  Key
} from 'lucide-react';


const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  // Authentication State
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [user, setUser] = useState(null);
  
  // App States
  const [todos, setTodos] = useState([]);
  const [filter, setFilter] = useState('all');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  
  // UI & Loading States
  const [loading, setLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);

  // Hugging Face Token Settings States
  const [googleLoaded, setGoogleLoaded] = useState(false);
  const [showHFConfig, setShowHFConfig] = useState(false);
  const [hfTokenInput, setHfTokenInput] = useState('');
  const [hfMsg, setHfMsg] = useState('');
  const [hfError, setHfError] = useState('');

  // Email/Password Authentication States
  const [authMode, setAuthMode] = useState('login');
  const [emailInput, setEmailInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  
  // Form States for Todo
  const [todoTitle, setTodoTitle] = useState('');
  const [todoDesc, setTodoDesc] = useState('');
  const [todoDeadline, setTodoDeadline] = useState('');
  const [currentEditTodo, setCurrentEditTodo] = useState(null);
  
  // Chat scroll anchor
  const chatEndRef = useRef(null);

  const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || 'your_google_client_id_here';

  const handleLogout = () => {
    setToken('');
    localStorage.removeItem('token');
    setUser(null);
    setTodos([]);
    setChatMessages([]);
  };

  // API Call: Fetch User Info
  const fetchUserData = async () => {
    try {
      const res = await fetch(`${API_URL}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        handleLogout();
      }
    } catch (err) {
      console.error("Error fetching user info:", err);
    }
  };

  // API Call: Fetch Todos
  const fetchTodos = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_URL}/api/todos`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setTodos(data);
      }
    } catch (err) {
      console.error("Error fetching todos:", err);
    } finally {
      setLoading(false);
    }
  };

  // API Call: Fetch Chat History
  const fetchChatHistory = async () => {
    try {
      const res = await fetch(`${API_URL}/api/chat/history`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setChatMessages(data.messages || []);
      }
    } catch (err) {
      console.error("Error fetching chat history:", err);
    }
  };

  // Auto-scroll chat history
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, chatLoading]);

  // Load User Details, Todos and Chat History upon authentication
  useEffect(() => {
    if (!token) {
      localStorage.removeItem('token');
      return;
    }
    localStorage.setItem('token', token);
    let isMounted = true;
    const loadData = async () => {
      try {
        const [userRes, todosRes, chatRes] = await Promise.all([
          fetch(`${API_URL}/api/auth/me`, { headers: { 'Authorization': `Bearer ${token}` } }),
          fetch(`${API_URL}/api/todos`, { headers: { 'Authorization': `Bearer ${token}` } }),
          fetch(`${API_URL}/api/chat/history`, { headers: { 'Authorization': `Bearer ${token}` } })
        ]);
        if (isMounted && userRes.ok) {
          const u = await userRes.json();
          setUser(u);
        }
        if (isMounted && todosRes.ok) {
          const t = await todosRes.json();
          setTodos(t);
        }
        if (isMounted && chatRes.ok) {
          const c = await chatRes.json();
          setChatMessages(c.messages || []);
        }
      } catch (err) {
        console.error("Error fetching initial data:", err);
      }
    };
    loadData();
    return () => { isMounted = false; };
  }, [token]);


  // Initialize and render Google Login button
  const handleGoogleCredentialResponse = async (response) => {
    setError('');
    const idToken = response.credential;
    try {
      const res = await fetch(`${API_URL}/api/auth/google-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: idToken })
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Lỗi khi xác thực tài khoản Google');
      }

      setToken(data.access_token);
    } catch (err) {
      setError(err.message);
    }
  };

  // Polling to wait for Google Sign-In script loading
  useEffect(() => {
    if (window.google) {
      const timer = setTimeout(() => setGoogleLoaded(true), 0);
      return () => clearTimeout(timer);
    }
    const interval = setInterval(() => {
      if (window.google) {
        setGoogleLoaded(true);
        clearInterval(interval);
      }
    }, 100);
    return () => clearInterval(interval);
  }, []);

  // Initialize and render Google Login button
  useEffect(() => {
    if (!token && googleLoaded && window.google) {
      if (!GOOGLE_CLIENT_ID || GOOGLE_CLIENT_ID === 'your_google_client_id_here') {
        console.warn("[Google Auth] Vui lòng cấu hình VITE_GOOGLE_CLIENT_ID hợp lệ trong tệp .env");
        return;
      }
      try {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleGoogleCredentialResponse,
        });
        
        const parent = document.getElementById('google-btn-parent');
        if (parent) {
          window.google.accounts.id.renderButton(
            parent,
            { theme: 'outline', size: 'large', width: '100%' }
          );
        }
      } catch (err) {
        console.error("Error initializing Google accounts SDK:", err);
      }
    }
  }, [token, googleLoaded, GOOGLE_CLIENT_ID]);


  // Actions: Save user's HF Token
  const handleSaveHFToken = async (e) => {
    e.preventDefault();
    setHfError('');
    setHfMsg('');
    if (!hfTokenInput.trim()) return;

    try {
      const res = await fetch(`${API_URL}/api/users/hf-token`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ hf_token: hfTokenInput.trim() })
      });
      const data = await res.json();
      
      if (res.ok) {
        setHfMsg(data.message || 'Đã lưu Token thành công!');
        setHfTokenInput('');
        fetchUserData(); // Reload user to update has_hf_token to true
        setTimeout(() => {
          setShowHFConfig(false);
          setHfMsg('');
        }, 1500);
      } else {
        throw new Error(data.detail || 'Lỗi khi lưu Token.');
      }
    } catch (err) {
      setHfError(err.message);
    }
  };

  // Actions: Delete user's HF Token
  const handleDeleteHFToken = async () => {
    if (!confirm("Bạn có chắc chắn muốn xóa Hugging Face Token? Tính năng chatbot sẽ không khả dụng cho tới khi cấu hình lại.")) return;
    setHfError('');
    setHfMsg('');

    try {
      const res = await fetch(`${API_URL}/api/users/hf-token`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      
      if (res.ok) {
        setHfMsg(data.message || 'Đã xóa Token!');
        setHfTokenInput('');
        fetchUserData(); // Reload user to update has_hf_token to false
        setTimeout(() => {
          setShowHFConfig(true); // Automatically show configuration input
          setHfMsg('');
        }, 1000);
      } else {
        throw new Error(data.detail || 'Lỗi khi xóa Token.');
      }
    } catch (err) {
      setHfError(err.message);
    }
  };


  const handleEmailAuthSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const email = emailInput.trim();
    const password = passwordInput;
    if (!email || !password) return;

    try {
      if (authMode === 'login') {
        const res = await fetch(`${API_URL}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (res.ok) {
          setToken(data.access_token);
        } else {
          throw new Error(data.detail || 'Email hoặc mật khẩu không chính xác.');
        }
      } else {
        const res = await fetch(`${API_URL}/api/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        if (res.ok) {
          const loginRes = await fetch(`${API_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
          });
          const loginData = await loginRes.json();
          if (loginRes.ok) {
            setToken(loginData.access_token);
          } else {
            throw new Error(loginData.detail || 'Đăng ký thành công nhưng đăng nhập thất bại.');
          }
        } else {
          throw new Error(data.detail || 'Lỗi khi đăng ký tài khoản.');
        }
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const IS_DEV_DEMO_ENABLED = import.meta.env.VITE_DEV_DEMO_ENABLED === 'true';

  const handleLocalBypassLogin = async () => {
    if (!IS_DEV_DEMO_ENABLED) {
      setError('Tính năng demo login bị tắt trong môi trường này.');
      return;
    }
    setError('');
    const email = import.meta.env.VITE_DEV_DEMO_EMAIL || 'testuser@gmail.com';
    const password = import.meta.env.VITE_DEV_DEMO_PASSWORD || 'testpassword123';
    try {
      // 1. Try to login
      let res = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      
      if (!res.ok) {
        // 2. If login fails, try to register
        const regRes = await fetch(`${API_URL}/api/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password })
        });
        
        if (regRes.ok) {
          // 3. Login again after successful registration
          res = await fetch(`${API_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
          });
        } else {
          const regData = await regRes.json();
          throw new Error(regData.detail || 'Không thể tạo tài khoản test cục bộ');
        }
      }
      
      if (res.ok) {
        const data = await res.json();
        setToken(data.access_token);
      } else {
        const data = await res.json();
        throw new Error(data.detail || 'Không thể đăng nhập tài khoản test');
      }
    } catch (err) {
      setError(err.message);
    }
  };


  // Actions: Create Todo
  const handleCreateTodo = async (e) => {
    e.preventDefault();
    setError('');
    if (!todoTitle.trim()) return;

    try {
      const res = await fetch(`${API_URL}/api/todos`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          title: todoTitle,
          description: todoDesc,
          deadline: todoDeadline ? new Date(todoDeadline).toISOString() : null
        })
      });

      if (res.ok) {
        fetchTodos();
        setShowAddModal(false);
        setTodoTitle('');
        setTodoDesc('');
        setTodoDeadline('');
      } else {
        const data = await res.json();
        throw new Error(data.detail || 'Lỗi khi tạo công việc');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Actions: Update Todo (from modal)
  const handleUpdateTodo = async (e) => {
    e.preventDefault();
    setError('');
    if (!currentEditTodo || !todoTitle.trim()) return;

    try {
      const res = await fetch(`${API_URL}/api/todos/${currentEditTodo.id}`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          title: todoTitle,
          description: todoDesc,
          status: currentEditTodo.status,
          deadline: todoDeadline ? new Date(todoDeadline).toISOString() : null
        })
      });

      if (res.ok) {
        fetchTodos();
        setShowEditModal(false);
        setCurrentEditTodo(null);
        setTodoTitle('');
        setTodoDesc('');
        setTodoDeadline('');
      } else {
        const data = await res.json();
        throw new Error(data.detail || 'Lỗi khi cập nhật công việc');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Actions: Toggle Complete
  const toggleTodoStatus = async (todo) => {
    const nextStatus = todo.status === 'completed' ? 'pending' : 'completed';
    try {
      const res = await fetch(`${API_URL}/api/todos/${todo.id}`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          status: nextStatus
        })
      });
      if (res.ok) {
        fetchTodos();
      }
    } catch (err) {
      console.error("Error toggling todo status:", err);
    }
  };

  // Actions: Delete Todo
  const handleDeleteTodo = async (id) => {
    if (!confirm("Bạn có chắc chắn muốn xóa công việc này?")) return;
    try {
      const res = await fetch(`${API_URL}/api/todos/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        fetchTodos();
      }
    } catch (err) {
      console.error("Error deleting todo:", err);
    }
  };

  // Actions: Open Edit Modal
  const openEditModal = (todo) => {
    setCurrentEditTodo(todo);
    setTodoTitle(todo.title);
    setTodoDesc(todo.description);
    if (todo.deadline) {
      // Convert UTC deadline to local datetime-local string
      const localDate = new Date(todo.deadline);
      const tzOffset = localDate.getTimezoneOffset() * 60000; // offset in milliseconds
      const localISOTime = (new Date(localDate - tzOffset)).toISOString().slice(0, 16);
      setTodoDeadline(localISOTime);
    } else {
      setTodoDeadline('');
    }
    setShowEditModal(true);
  };

  // Core API call to send a message to the chatbot
  const sendChatMessage = async (userMsg) => {
    if (!userMsg || !userMsg.trim() || chatLoading) return;
    const trimmedMsg = userMsg.trim();
    
    // Optimistic UI updates - append user message immediately
    setChatMessages(prev => [...prev, { sender: 'user', content: trimmedMsg, timestamp: new Date() }]);
    setChatLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ message: trimmedMsg })
      });
      
      if (res.ok) {
        const data = await res.json();
        // Append assistant message
        setChatMessages(prev => [...prev, { sender: 'assistant', content: data.response, timestamp: new Date() }]);
        
        // If the AI modified the database, reload todos automatically!
        if (data.should_refresh) {
          fetchTodos();
        }
      } else {
        const data = await res.json();
        setChatMessages(prev => [...prev, { 
          sender: 'assistant', 
          content: `⚠️ Có lỗi xảy ra: ${data.detail || 'Lỗi kết nối máy chủ.'}`, 
          timestamp: new Date() 
        }]);
      }
    } catch (err) {
      console.error("Chat error:", err);
      setChatMessages(prev => [...prev, { 
        sender: 'assistant', 
        content: "⚠️ Lỗi kết nối. Không thể liên lạc với Chatbot Agent.", 
        timestamp: new Date() 
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  // Actions: Chat Bot Submit
  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput;
    setChatInput('');
    await sendChatMessage(msg);
  };

  // Actions: Clear Chat History
  const handleClearChatHistory = async () => {
    if (!confirm("Xóa toàn bộ lịch sử trò chuyện?")) return;
    try {
      const res = await fetch(`${API_URL}/api/chat/history`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setChatMessages([]);
        fetchChatHistory();
      }

    } catch (err) {
      console.error("Error clearing chat history:", err);
    }
  };

  // Helper: Format Dates in View
  const formatDeadline = (deadlineStr) => {
    if (!deadlineStr) return null;
    const date = new Date(deadlineStr);
    return date.toLocaleString('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  };

  // Filter Logic
  const filteredTodos = todos.filter(todo => {
    if (filter === 'all') return true;
    return todo.status === filter;
  });

  // COUNT BADGES
  const countTodos = (status) => todos.filter(t => t.status === status).length;

  // --- RENDER GIAO DIỆN AUTH ---
  if (!token) {
    return (
      <div className="auth-container">
        <div className="auth-card">
          <div className="auth-header">
            <h1>Todo List AI</h1>
            <p>{authMode === 'login' ? 'Đăng nhập vào tài khoản của bạn' : 'Đăng ký tài khoản mới'}</p>
          </div>

          {error && <div className="error-alert"><AlertCircle size={16} style={{display:'inline', marginRight:5}}/> {error}</div>}

          <form onSubmit={handleEmailAuthSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>Địa chỉ Email *</label>
              <input 
                type="email" 
                className="input-field" 
                placeholder="email@gmail.com"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                required
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginTop: '4px' }}>
                Lưu ý: Chỉ chấp nhận đuôi @gmail.com
              </span>
            </div>

            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>Mật khẩu *</label>
              <input 
                type="password" 
                className="input-field" 
                placeholder="••••••••"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="auth-btn" style={{ marginTop: '10px' }}>
              {authMode === 'login' ? 'Đăng nhập' : 'Đăng ký'}
            </button>
          </form>

          <div className="auth-footer" style={{ marginTop: '20px' }}>
            {authMode === 'login' ? (
              <p>
                Chưa có tài khoản?{' '}
                <button 
                  type="button" 
                  className="auth-link" 
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                  onClick={() => setAuthMode('register')}
                >
                  Đăng ký ngay
                </button>
              </p>
            ) : (
              <p>
                Đã có tài khoản?{' '}
                <button 
                  type="button" 
                  className="auth-link" 
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                  onClick={() => setAuthMode('login')}
                >
                  Đăng nhập ngay
                </button>
              </p>
            )}
          </div>

          <div style={{ width: '100%', borderTop: '1px dashed rgba(255,255,255,0.15)', margin: '20px 0' }}></div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
            <div id="google-btn-parent" style={{ width: '100%', minHeight: '40px', display: 'flex', justifyContent: 'center' }}></div>
            
            {IS_DEV_DEMO_ENABLED && (
              <button 
                type="button"
                className="add-task-btn" 
                style={{ width: '100%', justifyContent: 'center', padding: '12px', background: 'linear-gradient(135deg, #4f46e5, #6366f1)', color: 'white', border: 'none' }}
                onClick={handleLocalBypassLogin}
              >
                Development demo login
              </button>
            )}
          </div>

        </div>
      </div>
    );
  }

  // --- RENDER DASHBOARD CHÍNH ---
  return (
    <div className="dashboard-container">
      <div className="bg-blob-3"></div>
      <div className="main-content">
        
        {/* Top Navbar */}
        <div className="top-bar">
          <div className="logo-section">
            <h2>
              <CheckCircle size={28} style={{color: '#6366f1'}} />
              Todo List AI
            </h2>
          </div>
          
          <div className="user-controls">
            <div className="user-email">
              <User size={14} style={{display: 'inline', marginRight: 6, verticalAlign: 'middle'}} />
              {user ? user.email : 'Gmail User'}
            </div>
            <button className="logout-btn" onClick={handleLogout}>
              <LogOut size={14} style={{display: 'inline', marginRight: 4, verticalAlign: 'middle'}} />
              Đăng xuất
            </button>
          </div>
        </div>

        {/* Global Error Banner */}
        {error && (
          <div className="error-alert" style={{display:'flex', alignItems:'center', justifyContent:'space-between'}}>
            <span>{error}</span>
            <X size={16} onClick={() => setError('')} style={{cursor:'pointer'}} />
          </div>
        )}

        {/* Dashboard Grid */}
        <div className="todo-dashboard-grid">
          
          {/* LEFT: Todos Panel */}
          <div>
            {/* Progress Dashboard Card */}
            {todos.length > 0 && (() => {
              const completedCount = countTodos('completed');
              const totalCount = todos.length;
              const percent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;
              return (
                <div className="progress-card">
                  <div className="progress-header">
                    <div className="progress-title">
                      <CheckCircle size={18} style={{ color: 'var(--color-completed)' }} />
                      Tiến độ hoàn thành công việc
                    </div>
                    <div className="progress-percent">{percent}%</div>
                  </div>
                  <div className="progress-track">
                    <div className="progress-bar" style={{ width: `${percent}%` }}></div>
                  </div>
                  <div className="stats-mini-grid">
                    <div className="stat-mini-card">
                      <span className="stat-val" style={{ color: 'var(--text-main)' }}>{totalCount}</span>
                      <span className="stat-lbl">Tổng số</span>
                    </div>
                    <div className="stat-mini-card">
                      <span className="stat-val" style={{ color: 'var(--color-pending)' }}>{countTodos('pending')}</span>
                      <span className="stat-lbl">Chưa làm</span>
                    </div>
                    <div className="stat-mini-card">
                      <span className="stat-val" style={{ color: 'var(--color-progress)' }}>{countTodos('in_progress')}</span>
                      <span className="stat-lbl">Đang làm</span>
                    </div>
                    <div className="stat-mini-card">
                      <span className="stat-val" style={{ color: 'var(--color-completed)' }}>{completedCount}</span>
                      <span className="stat-lbl">Đã xong</span>
                    </div>
                    <div className="stat-mini-card">
                      <span className="stat-val" style={{ color: 'var(--color-overdue)' }}>{countTodos('overdue')}</span>
                      <span className="stat-lbl">Trễ hạn</span>
                    </div>
                  </div>
                </div>
              );
            })()}

            <div className="todo-header-actions">
              <div className="filters-container">
                <button 
                  className={`filter-chip ${filter === 'all' ? 'active' : ''}`}
                  onClick={() => setFilter('all')}
                >
                  Tất cả ({todos.length})
                </button>
                <button 
                  className={`filter-chip ${filter === 'pending' ? 'active' : ''}`}
                  onClick={() => setFilter('pending')}
                >
                  Chưa làm ({countTodos('pending')})
                </button>
                <button 
                  className={`filter-chip ${filter === 'in_progress' ? 'active' : ''}`}
                  onClick={() => setFilter('in_progress')}
                >
                  Đang làm ({countTodos('in_progress')})
                </button>
                <button 
                  className={`filter-chip ${filter === 'completed' ? 'active' : ''}`}
                  onClick={() => setFilter('completed')}
                >
                  Đã xong ({countTodos('completed')})
                </button>
                <button 
                  className={`filter-chip ${filter === 'overdue' ? 'active' : ''}`}
                  onClick={() => setFilter('overdue')}
                >
                  Trễ hạn ({countTodos('overdue')})
                </button>
              </div>

              <button className="add-task-btn" onClick={() => {
                setTodoTitle('');
                setTodoDesc('');
                setTodoDeadline('');
                setShowAddModal(true);
              }}>
                <Plus size={18} />
                Thêm việc
              </button>
            </div>

            {/* List area */}
            {loading && todos.length === 0 ? (
              <div style={{textAlign:'center', padding: '40px', color: 'var(--text-muted)'}}>
                <RefreshCw size={24} className="animate-spin" style={{margin:'0 auto 10px'}}/>
                Đang tải dữ liệu...
              </div>
            ) : filteredTodos.length === 0 ? (
              <div className="empty-state">
                <CheckCircle size={48} />
                <h3>Không có công việc nào</h3>
                <p>Nhấp vào nút "Thêm việc" hoặc chat với trợ lý AI ở góc phải để tạo công việc mới.</p>
              </div>
            ) : (
              <div className="todo-list-container">
                {filteredTodos.map((todo, index) => (
                  <div 
                    key={todo.id} 
                    className={`todo-card status-${todo.status}`}
                    style={{ animationDelay: `${index * 40}ms` }}
                  >
                    
                    <div className="todo-card-header">
                      <div style={{flex: 1}}>
                        <div style={{display:'flex', alignItems:'center', gap: 10, marginBottom: 6}}>
                          <span className={`badge badge-${todo.status}`}>
                            {todo.status === 'completed' ? 'Hoàn thành' : 
                             todo.status === 'in_progress' ? 'Đang làm' :
                             todo.status === 'overdue' ? 'Trễ hạn' : 'Chưa làm'}
                          </span>
                          <span className="todo-title">{todo.title}</span>
                        </div>
                        {todo.description && <p className="todo-desc">{todo.description}</p>}
                      </div>

                      {/* Complete toggle */}
                      <button 
                        className="action-icon-btn btn-complete" 
                        onClick={() => toggleTodoStatus(todo)}
                        title={todo.status === 'completed' ? 'Đánh dấu chưa làm' : 'Đánh dấu hoàn thành'}
                      >
                        {todo.status === 'completed' ? (
                          <CheckCircle size={18} style={{color: 'var(--color-completed)'}} />
                        ) : (
                          <Circle size={18} />
                        )}
                      </button>
                    </div>

                    <div className="todo-card-footer">
                      <div className="todo-meta">
                        {todo.deadline && (
                          <span className="todo-deadline">
                            <Clock size={12} />
                            Hạn: {formatDeadline(todo.deadline)}
                          </span>
                        )}
                      </div>
                      
                      <div className="todo-actions">
                        <button 
                          className="action-icon-btn" 
                          onClick={() => openEditModal(todo)}
                          title="Sửa công việc"
                        >
                          <Edit3 size={14} />
                        </button>
                        <button 
                          className="action-icon-btn btn-delete" 
                          onClick={() => handleDeleteTodo(todo.id)}
                          title="Xóa công việc"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                  </div>
                ))}
              </div>
            )}
          </div>

          {/* RIGHT: AI Chatbot Panel */}
          <div>
            <div className="chatbot-panel">
              <div className="chatbot-header">
                <div className="chatbot-title">
                  <Bot size={20} style={{color:'var(--color-progress)'}} />
                  <h4>Trợ lý AI</h4>
                  <span>Online</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {user && user.has_hf_token && !showHFConfig && (
                    <button 
                      className="chatbot-clear-btn" 
                      onClick={() => {
                        setShowHFConfig(true);
                        setHfError('');
                        setHfMsg('');
                      }}
                      title="Cấu hình Token"
                      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >
                      <Key size={14} />
                    </button>
                  )}
                  {chatMessages.length > 0 && !showHFConfig && (user && user.has_hf_token) && (
                    <button className="chatbot-clear-btn" onClick={handleClearChatHistory}>
                      Xóa lịch sử
                    </button>
                  )}
                </div>
              </div>

              {showHFConfig || (user && !user.has_hf_token) ? (
                <div className="chatbot-history" style={{ display: 'flex', flexDirection: 'column', padding: '24px', gap: '16px', justifyContent: 'center', height: '100%' }}>
                  <div style={{ textAlign: 'center', marginBottom: '10px' }}>
                    <Key size={36} style={{ color: 'var(--color-progress)', margin: '0 auto 12px' }} />
                    <h4 style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '8px' }}>
                      Cấu hình Hugging Face Token
                    </h4>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                      Để sử dụng tính năng Chatbot AI, vui lòng nhập Hugging Face API Token cá nhân của bạn.
                      Bạn có thể lấy hoặc tạo token tại <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--primary)', textDecoration: 'underline' }}>huggingface.co/settings/tokens</a>.
                    </p>
                  </div>

                  <form onSubmit={handleSaveHFToken} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <input 
                      type="password"
                      className="chatbot-input"
                      placeholder="hf_..."
                      value={hfTokenInput}
                      onChange={(e) => setHfTokenInput(e.target.value)}
                      required
                      style={{ width: '100%', background: 'rgba(0,0,0,0.3)' }}
                    />
                    {hfError && <div className="error-alert" style={{ margin: 0, padding: '8px', fontSize: '0.78rem' }}>{hfError}</div>}
                    {hfMsg && <div style={{ color: 'var(--color-completed)', fontSize: '0.78rem', textAlign: 'center', fontWeight: 500 }}>{hfMsg}</div>}
                    
                    <button type="submit" className="auth-btn" style={{ margin: 0, padding: '10px' }}>
                      Lưu Token
                    </button>
                  </form>

                  <div style={{ display: 'flex', gap: '10px', marginTop: '10px', justifyContent: 'center' }}>
                    {user && user.has_hf_token && (
                      <>
                        <button 
                          type="button" 
                          className="btn-secondary" 
                          style={{ padding: '8px 16px', fontSize: '0.8rem', flex: 1 }}
                          onClick={() => {
                            setShowHFConfig(false);
                            setHfError('');
                            setHfMsg('');
                          }}
                        >
                          Quay lại
                        </button>
                        <button 
                          type="button" 
                          className="logout-btn" 
                          style={{ padding: '8px 16px', fontSize: '0.8rem', flex: 1 }}
                          onClick={handleDeleteHFToken}
                        >
                          Xóa Token
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                <>
                  {/* Chat timeline */}
                  <div className="chatbot-history">
                    {chatMessages.length === 0 ? (
                      <div style={{
                        display:'flex', 
                        flexDirection:'column', 
                        alignItems:'center', 
                        justifyContent:'center', 
                        height:'100%', 
                        color:'var(--text-muted)',
                        textAlign:'center',
                        padding: 20
                      }}>
                        <MessageSquare size={36} style={{marginBottom: 10, opacity: 0.5}} />
                        <p style={{fontSize:'0.9rem'}}>Chào bạn! Tôi là chatbot quản lý công việc.</p>
                        <p style={{fontSize:'0.8rem', marginTop: 4}}>Bạn có thể yêu cầu tôi tạo, hoàn thành, xóa công việc hoặc tra cứu trực tiếp bằng giọng điệu tự nhiên.</p>
                      </div>
                    ) : (
                      chatMessages.map((msg, index) => (
                        <div key={index} className={`chat-bubble ${msg.sender}`}>
                          {msg.content}
                        </div>
                      ))
                    )}
                    
                    {chatLoading && (
                      <div className="chat-bubble assistant typing">
                        <Bot size={16} className="animate-spin" style={{ color: 'var(--color-progress)' }} />
                        <div className="typing-dots">
                          <div className="typing-dot"></div>
                          <div className="typing-dot"></div>
                          <div className="typing-dot"></div>
                        </div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  {/* Chat suggested command chips */}
                  <div className="suggested-chips-container">
                    <div className="suggested-chips-label">Lệnh nhanh trợ lý AI</div>
                    <div className="suggested-chips">
                      <button 
                        type="button" 
                        className="chip-btn" 
                        onClick={() => sendChatMessage('Tạo việc "Học React ngày mai"')}
                        disabled={chatLoading}
                      >
                        📝 Học React
                      </button>
                      <button 
                        type="button" 
                        className="chip-btn" 
                        onClick={() => sendChatMessage('Cập nhật tất cả công việc sang đã xong')}
                        disabled={chatLoading}
                      >
                        ✅ Hoàn thành hết
                      </button>
                      <button 
                        type="button" 
                        className="chip-btn" 
                        onClick={() => sendChatMessage('Có công việc nào trễ hạn không?')}
                        disabled={chatLoading}
                      >
                        ⏰ Việc trễ hạn
                      </button>
                      <button 
                        type="button" 
                        className="chip-btn" 
                        onClick={() => sendChatMessage('Báo cáo tiến độ các công việc hiện tại của tôi')}
                        disabled={chatLoading}
                      >
                        📊 Tóm tắt tiến độ
                      </button>
                    </div>
                  </div>

                  {/* Chat Send Form */}
                  <form className="chatbot-input-area" onSubmit={handleChatSubmit}>
                    <input 
                      type="text" 
                      className="chatbot-input" 
                      placeholder="Thêm công việc học React, hỏi đáp..."
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      disabled={chatLoading}
                    />
                    <button type="submit" className="chatbot-send-btn" disabled={chatLoading || !chatInput.trim()}>
                      <Send size={18} />
                    </button>
                  </form>
                </>
              )}
            </div>
          </div>

        </div>
      </div>

      {/* --- ADD TASK DIALOG MODAL --- */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Thêm công việc mới</h3>
              <button className="modal-close-btn" onClick={() => setShowAddModal(false)}>
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleCreateTodo}>
              <div className="form-group">
                <label>Tiêu đề *</label>
                <input 
                  type="text" 
                  className="input-field" 
                  placeholder="Ví dụ: Học lập trình Python"
                  value={todoTitle}
                  onChange={(e) => setTodoTitle(e.target.value)}
                  required
                />
              </div>
              
              <div className="form-group">
                <label>Mô tả chi tiết</label>
                <textarea 
                  className="input-field" 
                  rows="3"
                  placeholder="Mô tả nội dung công việc cần làm..."
                  value={todoDesc}
                  onChange={(e) => setTodoDesc(e.target.value)}
                  style={{resize:'vertical'}}
                />
              </div>

              <div className="form-group">
                <label>Hạn chót (Deadline)</label>
                <input 
                  type="datetime-local" 
                  className="input-field"
                  value={todoDeadline}
                  onChange={(e) => setTodoDeadline(e.target.value)}
                />
              </div>

              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => setShowAddModal(false)}>
                  Hủy bỏ
                </button>
                <button type="submit" className="btn-primary">
                  Tạo công việc
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- EDIT TASK DIALOG MODAL --- */}
      {showEditModal && currentEditTodo && (
        <div className="modal-overlay">
          <div className="modal-card">
            <div className="modal-header">
              <h3>Chỉnh sửa công việc</h3>
              <button className="modal-close-btn" onClick={() => {
                setShowEditModal(false);
                setCurrentEditTodo(null);
              }}>
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleUpdateTodo}>
              <div className="form-group">
                <label>Tiêu đề *</label>
                <input 
                  type="text" 
                  className="input-field" 
                  value={todoTitle}
                  onChange={(e) => setTodoTitle(e.target.value)}
                  required
                />
              </div>
              
              <div className="form-group">
                <label>Mô tả chi tiết</label>
                <textarea 
                  className="input-field" 
                  rows="3"
                  value={todoDesc}
                  onChange={(e) => setTodoDesc(e.target.value)}
                  style={{resize:'vertical'}}
                />
              </div>

              <div className="form-group">
                <label>Trạng thái</label>
                <select 
                  className="input-field" 
                  value={currentEditTodo.status}
                  onChange={(e) => setCurrentEditTodo({
                    ...currentEditTodo,
                    status: e.target.value
                  })}
                >
                  <option value="pending">Chưa làm (Pending)</option>
                  <option value="in_progress">Đang làm (In Progress)</option>
                  <option value="completed">Đã xong (Completed)</option>
                  <option value="overdue">Trễ hạn (Overdue)</option>
                </select>
              </div>

              <div className="form-group">
                <label>Hạn chót (Deadline)</label>
                <input 
                  type="datetime-local" 
                  className="input-field"
                  value={todoDeadline}
                  onChange={(e) => setTodoDeadline(e.target.value)}
                />
              </div>

              <div className="modal-footer">
                <button type="button" className="btn-secondary" onClick={() => {
                  setShowEditModal(false);
                  setCurrentEditTodo(null);
                }}>
                  Hủy bỏ
                </button>
                <button type="submit" className="btn-primary">
                  Cập nhật
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}

export default App;

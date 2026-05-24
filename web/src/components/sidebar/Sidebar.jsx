import React from 'react';
import {
  LayoutDashboard,
  Settings,
  Layers,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Cpu,
  LineChart,
  BarChart3,
  HelpCircle,
  Bell
} from 'lucide-react';

const SidebarItem = ({ icon: Icon, label, active, onClick, collapsed, badge }) => (
  <button
    onClick={onClick}
    className={`relative w-full flex items-center ${collapsed ? 'justify-center' : 'gap-3 px-3'} py-2.5 rounded-xl transition-all duration-200 group focus:outline-none ${active
      ? 'bg-gradient-to-r from-white/10 to-white/5 text-white border border-white/10 shadow-lg shadow-black/20'
      : 'text-slate-400 hover:bg-white/5 hover:text-slate-200 border border-transparent'
      }`}
  >
    <div className="relative flex-shrink-0">
        <Icon className={`w-5 h-5 ${active ? 'text-white' : 'group-hover:scale-110 duration-200'}`} />
        {badge > 0 && collapsed && (
            <span className="absolute -top-1.5 -right-1.5 flex h-3 w-3 items-center justify-center rounded-full bg-rose-500 text-[8px] font-bold text-white shadow-sm ring-1 ring-[#0a0d0f]">
            </span>
        )}
    </div>
    {!collapsed && (
        <div className="flex flex-1 items-center justify-between min-w-0">
            <span className="text-sm font-medium truncate">{label}</span>
            {badge > 0 && (
                <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-black text-white shadow-sm shadow-rose-500/20">
                    {badge > 99 ? '99+' : badge}
                </span>
            )}
        </div>
    )}
  </button>
);

const Sidebar = ({
  activeTab,
  onTabChange,
  user,
  onSignOut,
  llmConfig,
  collapsed,
  setCollapsed,
  unreadNotificationCount,
  onOpenNotifications
}) => {
  const menuItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: '控制台' },
    { id: 'strategies', icon: Layers, label: '策略库' },
    { id: 'backtest', icon: BarChart3, label: '回测' },
    { id: 'market', icon: LineChart, label: '看盘' },
    { id: 'settings', icon: Settings, label: '系统设置' },
  ];

  return (
    <aside
      className={`flex flex-col bg-[#0a0d0f] border-r border-white/5 transition-all duration-300 relative z-50 ${collapsed ? 'w-16' : 'w-56'
        }`}
    >
      {/* Header / Logo */}
      <div className={`h-16 flex items-center overflow-hidden border-b border-white/5 transition-all ${collapsed ? 'justify-center px-0' : 'px-6 gap-3'}`}>
        <div className="min-w-[40px] h-10 bg-emerald-600/10 rounded-xl flex items-center justify-center border border-emerald-500/20">
          <img
            src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
            alt="Logo"
            className="w-7 h-7 object-contain"
          />
        </div>
        {!collapsed && (
          <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent whitespace-nowrap">
            OG AI
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className={`flex-1 ${collapsed ? 'px-2' : 'px-3'} py-6 space-y-2 overflow-y-auto custom-scrollbar`}>
        {menuItems.map((item) => (
          <SidebarItem
            key={item.id}
            icon={item.icon}
            label={item.label}
            active={activeTab === item.id}
            onClick={() => onTabChange(item.id)}
            collapsed={collapsed}
          />
        ))}

      </nav>

      {/* Bottom Section: Notifications & Help */}
      <div className={`p-3 border-t border-white/5 transition-all duration-300 space-y-1`}>
        <SidebarItem
          icon={Bell}
          label="消息通知"
          active={false}
          onClick={onOpenNotifications}
          collapsed={collapsed}
          badge={unreadNotificationCount}
        />
        <SidebarItem
          icon={HelpCircle}
          label="帮助与反馈"
          active={activeTab === 'help'}
          onClick={() => onTabChange('help')}
          collapsed={collapsed}
        />
      </div>

      {/* Collapse Toggle Bubble */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3.5 top-1/2 -translate-y-1/2 w-7 h-7 bg-[#0a0d0f] border border-white/10 rounded-full flex items-center justify-center text-slate-400 hover:text-white hover:bg-emerald-600 hover:border-emerald-600 hover:shadow-[0_0_15px_rgba(16,185,129,0.5)] transition-all z-10 group shadow-lg focus:outline-none"
      >
        {collapsed ? <ChevronRight className="w-4 h-4 ml-0.5" /> : <ChevronLeft className="w-4 h-4 pr-0.5" />}
      </button>
    </aside>
  );
};

export default Sidebar;
// 迫于篇幅，css 中需补充 custom-scrollbar 相关定义，已在 index.css 中包含。

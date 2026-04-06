import React, { useState, useRef, useEffect } from 'react';
import { 
  Settings, LogOut, User, ChevronDown, Cpu
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

const UserMenu = ({ user, onSignOut, onOpenSettings }) => {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSignOut = async () => {
    setIsOpen(false);
    if (onSignOut) await onSignOut();
  };

  const displayName = user?.user_metadata?.full_name || 
                     user?.user_metadata?.name || 
                     (user?.email && !user.email.includes('@wallet.local') ? user.email.split('@')[0] : 'User');

  const avatarUrl = user?.user_metadata?.picture || user?.user_metadata?.avatar_url;

  return (
    <div className="relative" ref={menuRef}>
      {/* Trigger */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 p-1 pr-3 rounded-full bg-slate-800/50 hover:bg-slate-700/50 transition-all border border-white/5 active:scale-95"
      >
        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-violet-500 flex items-center justify-center overflow-hidden shadow-inner flex-shrink-0">
          {avatarUrl ? (
            <img src={avatarUrl} alt="avatar" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
          ) : (
            <span className="text-white text-xs font-bold">{displayName[0]?.toUpperCase()}</span>
          )}
        </div>
        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-[#1C2127] border border-white/10 rounded-2xl shadow-2xl py-2 z-50 animate-in fade-in zoom-in-95 duration-200">
          {/* User Info Section */}
          <div className="px-4 py-3 border-b border-white/5 mb-2">
            <p className="text-sm font-semibold text-white truncate">{displayName}</p>
            <p className="text-xs text-slate-400 truncate mt-0.5">{user?.email || 'Strategy Trader'}</p>
          </div>

          {/* Menu Items */}
          <button
            onClick={() => {
              if (onOpenSettings) onOpenSettings();
              setIsOpen(false);
            }}
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:bg-white/5 transition-colors text-left"
          >
            <Settings className="w-4 h-4 text-slate-400" />
            <span>{t('auth.settings')}</span>
          </button>

          <div className="h-px bg-white/5 my-1 mx-2" />

          <button
            onClick={handleSignOut}
            className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-400 hover:bg-red-400/10 transition-colors text-left"
          >
            <LogOut className="w-4 h-4" />
            <span>{t('auth.signOut')}</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default UserMenu;

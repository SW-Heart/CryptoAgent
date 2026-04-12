import React, { useRef } from 'react';
import Button from '../components/common/Button';
import { Terminal } from 'lucide-react';

const LandingPage = ({ onStart }) => {
  const btnRef = useRef(null);

  const handleMouseEnter = () => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    window.dispatchEvent(new CustomEvent('FOCUS_BTN_AREA', {
      detail: { 
         x: rect.left, 
         y: rect.top, 
         w: rect.width, 
         h: rect.height, 
         cx: rect.left + rect.width / 2, 
         cy: rect.top + rect.height / 2, 
         active: true 
      }
    }));
  };

  const handleMouseLeave = () => {
    window.dispatchEvent(new CustomEvent('FOCUS_BTN_AREA', { detail: { active: false } }));
  };

  return (
    <div className="h-full w-full relative flex flex-col items-center justify-center z-10 bg-transparent pointer-events-none">
      <div className="flex flex-col items-center text-center px-4 animate-in fade-in slide-in-from-bottom-8 duration-1000 z-20 pointer-events-auto">

        <div className="flex items-center gap-3 mb-10">
          <img
            src="https://ai-shot.oss-cn-hangzhou.aliyuncs.com/logo/ailogo.png"
            alt="OG AI Logo"
            className="w-10 h-10 object-contain drop-shadow-md"
          />
          <span className="text-2xl font-light tracking-tight text-white/80">OG AI</span>
        </div>

        <h1 className="text-5xl md:text-[5.5rem] font-medium mb-20 text-slate-100 leading-[1.05] tracking-tight max-w-5xl drop-shadow-[0_0_30px_rgba(255,255,255,0.08)]">
          计划你的交易 交易你的计划
        </h1>

        <button
          ref={btnRef}
          onClick={onStart}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          className="relative group px-10 py-4 rounded-md transition-all duration-700 text-white/60 hover:text-white/100 bg-transparent border border-white/10 hover:border-white/5 cursor-pointer overflow-visible shadow-[0_0_10px_rgba(255,255,255,0.01)] hover:shadow-none"
        >
          {/* 这里剥除了明显的背景抢夺，仅使用 hover 的环境背景做一点辅助底色 */}
          <div className="absolute inset-0 bg-transparent group-hover:bg-white/5 backdrop-blur-sm transition-all duration-700 pointer-events-none rounded-md" />
          <span className="relative z-10 flex items-center justify-center font-light tracking-[0.3em] text-[0.8rem] uppercase drop-shadow-[0_0_8px_rgba(255,255,255,0.5)]">
            {/* 顶级的极品终端标识符号，代替常规图标 */}
            <span className="font-mono text-white/30 tracking-normal mr-4 text-lg font-medium transition-all duration-500 group-hover:opacity-100 group-hover:text-[#4b8cff] group-hover:scale-105">
              &gt;_
            </span>
            进入控制中枢
          </span>
        </button>
      </div>
    </div>
  );
};

export default LandingPage;

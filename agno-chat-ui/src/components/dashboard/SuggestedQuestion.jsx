import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * SuggestedQuestion - 动态推荐问题组件
 * 根据每日日报AI生成问题，用户点击后切换到下一个
 */
export default function SuggestedQuestion({ userId, onFillInput }) {
    const { i18n, t } = useTranslation();
    const [question, setQuestion] = useState('');
    const [currentIndex, setCurrentIndex] = useState(0);
    const [allQuestions, setAllQuestions] = useState([]);
    const [isHovered, setIsHovered] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    // 获取当前语言
    const language = i18n.language?.startsWith('zh') ? 'zh' : 'en';

    // 加载推荐问题
    useEffect(() => {
        const fetchQuestions = async () => {
            try {
                const url = new URL(`${BASE_URL}/api/suggested-questions`);
                url.searchParams.set('language', language);
                if (userId) {
                    url.searchParams.set('user_id', userId);
                }

                const res = await fetch(url);
                const data = await res.json();

                setQuestion(data.question || '');
                setCurrentIndex(data.current_index || 0);
                setAllQuestions(data.all_questions || []);
            } catch (err) {
                console.error('[SuggestedQuestion] Error fetching:', err);
                // 加载失败时使用默认问题
                const defaults = language === 'zh'
                    ? ['今天市场怎么走？', 'BTC 能买吗？', '什么板块最火？']
                    : ['Market outlook today?', 'Should I buy BTC?', 'What sectors are hot?'];
                setQuestion(defaults[0]);
                setAllQuestions(defaults);
            } finally {
                setIsLoading(false);
            }
        };

        fetchQuestions();
    }, [userId, language]);

    // 处理点击
    const handleClick = async () => {
        // 立即填充到输入框
        if (onFillInput && question) {
            onFillInput(question);
        }

        // 切换到下一个问题
        const nextIndex = (currentIndex + 1) % allQuestions.length;
        setCurrentIndex(nextIndex);
        setQuestion(allQuestions[nextIndex] || question);

        // 记录点击
        if (userId) {
            try {
                await fetch(`${BASE_URL}/api/suggested-questions/click`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: userId,
                        question_index: currentIndex
                    })
                });
            } catch (err) {
                console.error('[SuggestedQuestion] Error recording click:', err);
            }
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-3">
                <div className="w-6 h-6 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
            </div>
        );
    }

    return (
        <div className="flex items-center justify-center py-3">
            {/* 整个卡片都是可点击按钮 */}
            <button
                onClick={handleClick}
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
                className={`
                    relative cursor-pointer
                    transition-all duration-300 ease-out
                    ${isHovered ? '-translate-y-1' : 'translate-y-0'}
                `}
                style={{ maxWidth: '600px' }}
            >
                {/* 毛玻璃背景层 */}
                <div
                    className={`
                        absolute inset-0 rounded-2xl transition-all duration-300 ease-out
                        ${isHovered
                            ? 'bg-white/5 backdrop-blur-md border border-white/10 shadow-xl shadow-indigo-500/10'
                            : 'bg-transparent border border-transparent'
                        }
                    `}
                />

                {/* 内容区域 */}
                <div className="relative flex items-center gap-4 px-6 py-4">
                    {/* 问题文本 */}
                    <h2 className="text-2xl md:text-3xl lg:text-4xl font-bold bg-gradient-to-r from-orange-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
                        {question}
                    </h2>

                    {/* 右侧箭头图标 - hover时淡入 */}
                    <span
                        className={`
                            text-2xl transition-all duration-300 ease-out flex-shrink-0
                            ${isHovered
                                ? 'opacity-100 translate-x-0 text-indigo-400'
                                : 'opacity-0 -translate-x-2 text-indigo-400'
                            }
                        `}
                        style={{
                            textShadow: isHovered ? '0 0 12px rgba(129, 140, 248, 0.6)' : 'none'
                        }}
                    >
                        ➔
                    </span>
                </div>
            </button>
        </div>
    );
}




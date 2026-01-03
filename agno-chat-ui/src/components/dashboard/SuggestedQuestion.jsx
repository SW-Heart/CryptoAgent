import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { SuggestedQuestionSkeleton } from './Skeleton';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// 模块级缓存：避免页面切换时重复请求
// 格式: { [language]: { questions: [], timestamp: number, index: number } }
const questionsCache = {};
const CACHE_DURATION = 10 * 60 * 1000; // 10 分钟缓存

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

    // 加载推荐问题（带缓存）
    useEffect(() => {
        const fetchQuestions = async () => {
            // 检查缓存是否有效
            const cached = questionsCache[language];
            const now = Date.now();

            if (cached && (now - cached.timestamp < CACHE_DURATION) && cached.questions.length > 0) {
                // 使用缓存数据
                console.log('[SuggestedQuestion] Using cached questions');
                setAllQuestions(cached.questions);
                setCurrentIndex(cached.index);
                setQuestion(cached.questions[cached.index] || cached.questions[0]);
                setIsLoading(false);
                return;
            }

            // 无缓存或已过期，请求新数据
            try {
                const url = new URL(`${BASE_URL}/api/suggested-questions`);
                url.searchParams.set('language', language);
                if (userId) {
                    url.searchParams.set('user_id', userId);
                }

                const res = await fetch(url);
                const data = await res.json();

                const questions = data.all_questions || [];
                const index = data.current_index || 0;
                const currentQuestion = data.question || questions[0] || '';

                // 更新缓存
                questionsCache[language] = {
                    questions,
                    timestamp: now,
                    index
                };

                setQuestion(currentQuestion);
                setCurrentIndex(index);
                setAllQuestions(questions);
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

        // 同步更新缓存中的 index
        if (questionsCache[language]) {
            questionsCache[language].index = nextIndex;
        }

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
        return <SuggestedQuestionSkeleton />;
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
                style={{ maxWidth: '768px' }}
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




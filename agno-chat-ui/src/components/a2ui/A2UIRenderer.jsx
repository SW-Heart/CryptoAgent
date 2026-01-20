/**
 * A2UI Renderer - A2UI 协议渲染引擎
 * 
 * 将 Agent 返回的 A2UI JSON 解析并渲染为 React 组件。
 * 支持的组件类型：card, button, text, row, column, divider, icon, badge
 */

import React from 'react';
import SwapCard from './SwapCard';
import { ArrowRight, ArrowDown, Check, X, AlertTriangle, Info } from 'lucide-react';

// ==========================================
// 组件映射表
// ==========================================

// 图标映射
const ICON_MAP = {
    'arrow-right': ArrowRight,
    'arrow-down': ArrowDown,
    'check': Check,
    'x': X,
    'alert': AlertTriangle,
    'info': Info,
};

// 样式映射
const TEXT_STYLES = {
    heading: 'text-xl font-bold',
    subheading: 'text-lg font-semibold',
    body: 'text-sm',
    caption: 'text-xs',
    label: 'text-xs font-medium uppercase tracking-wide',
    mono: 'font-mono text-sm',
};

const COLOR_STYLES = {
    primary: 'text-blue-400',
    secondary: 'text-slate-400',
    success: 'text-emerald-400',
    danger: 'text-red-400',
    warning: 'text-amber-400',
    muted: 'text-slate-500',
};

// ==========================================
// 基础组件
// ==========================================

const Text = ({ value, style = 'body', color }) => {
    const textClass = TEXT_STYLES[style] || TEXT_STYLES.body;
    const colorClass = color ? COLOR_STYLES[color] : '';
    return <span className={`${textClass} ${colorClass}`}>{value}</span>;
};

const Icon = ({ name, size = 'md', color }) => {
    const IconComponent = ICON_MAP[name];
    if (!IconComponent) return null;

    const sizeClass = {
        sm: 'w-4 h-4',
        md: 'w-5 h-5',
        lg: 'w-6 h-6',
    }[size] || 'w-5 h-5';

    const colorClass = color ? COLOR_STYLES[color] : 'text-slate-400';

    return <IconComponent className={`${sizeClass} ${colorClass}`} />;
};

const Button = ({ label, variant = 'primary', action_id, action_params, onAction, disabled }) => {
    const variantStyles = {
        primary: 'bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white shadow-lg shadow-blue-500/25',
        secondary: 'bg-slate-700 hover:bg-slate-600 text-slate-200 border border-slate-600',
        danger: 'bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/50',
        success: 'bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/50',
        ghost: 'hover:bg-slate-700/50 text-slate-300',
    };

    const handleClick = () => {
        if (onAction && action_id) {
            onAction(action_id, action_params || {});
        }
    };

    return (
        <button
            onClick={handleClick}
            disabled={disabled}
            className={`
        px-4 py-2 rounded-lg font-medium text-sm
        transition-all duration-200
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variantStyles[variant] || variantStyles.primary}
      `}
        >
            {label}
        </button>
    );
};

const Row = ({ children, justify = 'start', align = 'center', gap = 'md' }) => {
    const justifyClass = {
        start: 'justify-start',
        center: 'justify-center',
        end: 'justify-end',
        'space-between': 'justify-between',
        'space-around': 'justify-around',
    }[justify] || 'justify-start';

    const alignClass = {
        start: 'items-start',
        center: 'items-center',
        end: 'items-end',
        stretch: 'items-stretch',
    }[align] || 'items-center';

    const gapClass = {
        xs: 'gap-1',
        sm: 'gap-2',
        md: 'gap-4',
        lg: 'gap-6',
    }[gap] || 'gap-4';

    return (
        <div className={`flex ${justifyClass} ${alignClass} ${gapClass}`}>
            {children}
        </div>
    );
};

const Column = ({ children, align = 'start', gap = 'md' }) => {
    const alignClass = {
        start: 'items-start',
        center: 'items-center',
        end: 'items-end',
        stretch: 'items-stretch',
    }[align] || 'items-start';

    const gapClass = {
        xs: 'gap-1',
        sm: 'gap-2',
        md: 'gap-4',
        lg: 'gap-6',
    }[gap] || 'gap-4';

    return (
        <div className={`flex flex-col ${alignClass} ${gapClass}`}>
            {children}
        </div>
    );
};

const Divider = () => (
    <div className="w-full h-px bg-gradient-to-r from-transparent via-slate-600 to-transparent my-3" />
);

const Card = ({ children, title, variant = 'default', padding = 'lg' }) => {
    const paddingClass = {
        sm: 'p-3',
        md: 'p-4',
        lg: 'p-6',
    }[padding] || 'p-6';

    const variantStyles = {
        default: 'bg-slate-800/50 border border-slate-700',
        elevated: 'bg-gradient-to-br from-slate-800 to-slate-900 border border-slate-600 shadow-xl shadow-black/30',
        glass: 'bg-slate-800/30 backdrop-blur-lg border border-slate-500/30',
    }[variant] || '';

    return (
        <div className={`rounded-xl ${variantStyles} ${paddingClass}`}>
            {title && (
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <span className="w-1 h-5 bg-gradient-to-b from-blue-400 to-purple-500 rounded-full" />
                    {title}
                </h3>
            )}
            <div className="flex flex-col gap-3">
                {children}
            </div>
        </div>
    );
};

// ==========================================
// A2UI 渲染器
// ==========================================

/**
 * A2UI Renderer 组件
 * 
 * @param {Object} surface - A2UI Surface JSON 对象
 * @param {Function} onAction - Action 回调函数 (actionId, params) => void
 */
const A2UIRenderer = ({ surface, onAction }) => {
    if (!surface || !surface.surface) {
        console.warn('[A2UIRenderer] Invalid surface:', surface);
        return null;
    }

    const { components } = surface.surface;
    if (!components || !Array.isArray(components)) {
        console.warn('[A2UIRenderer] Invalid components:', components);
        return null;
    }

    // 创建组件 ID -> 组件数据的映射
    const componentMap = {};
    components.forEach(comp => {
        componentMap[comp.id] = comp;
    });

    // 递归渲染组件
    const renderComponent = (componentId) => {
        const comp = componentMap[componentId];
        if (!comp) {
            console.warn(`[A2UIRenderer] Component not found: ${componentId}`);
            return null;
        }

        const { type, props = {}, children = [] } = comp;

        // 渲染子组件
        const renderedChildren = children.map(childId => (
            <React.Fragment key={childId}>
                {renderComponent(childId)}
            </React.Fragment>
        ));

        // 根据类型渲染对应组件
        switch (type) {
            case 'text':
                return <Text key={comp.id} {...props} />;

            case 'icon':
                return <Icon key={comp.id} {...props} />;

            case 'button':
                return <Button key={comp.id} {...props} onAction={onAction} />;

            case 'row':
                return <Row key={comp.id} {...props}>{renderedChildren}</Row>;

            case 'column':
                return <Column key={comp.id} {...props}>{renderedChildren}</Column>;

            case 'divider':
                return <Divider key={comp.id} />;

            case 'card':
                return <Card key={comp.id} {...props}>{renderedChildren}</Card>;

            default:
                console.warn(`[A2UIRenderer] Unknown component type: ${type}`);
                return null;
        }
    };

    // 找到根组件（通常是第一个 card）
    const rootComponent = components.find(c => c.type === 'card') || components[0];

    return (
        <div className="a2ui-surface my-4">
            {renderComponent(rootComponent.id)}
        </div>
    );
};

/**
 * 从 Markdown 文本中提取并渲染 A2UI 块
 * 
 * @param {string} content - 包含 ```a2ui 代码块的 Markdown 文本
 * @param {Function} onAction - Action 回调函数
 * @returns {Object} { hasA2UI: boolean, a2uiBlocks: Array, cleanContent: string }
 */
export const extractA2UIBlocks = (content) => {
    const a2uiPattern = /```a2ui\n([\s\S]*?)\n```/g;
    const blocks = [];
    let match;

    while ((match = a2uiPattern.exec(content)) !== null) {
        try {
            const surfaceJson = JSON.parse(match[1]);
            blocks.push({
                raw: match[0],
                surface: surfaceJson,
                startIndex: match.index,
                endIndex: match.index + match[0].length,
            });
        } catch (e) {
            console.warn('[A2UI] Failed to parse JSON:', e);
        }
    }

    // 清理内容（移除 a2ui 代码块）
    const cleanContent = content.replace(a2uiPattern, '').trim();

    return {
        hasA2UI: blocks.length > 0,
        a2uiBlocks: blocks,
        cleanContent,
    };
};

/**
 * 渲染消息内容，自动处理 A2UI 块
 */
export const renderMessageWithA2UI = (content, onAction) => {
    const { hasA2UI, a2uiBlocks, cleanContent } = extractA2UIBlocks(content);

    if (!hasA2UI) {
        return null;
    }

    return (
        <div className="a2ui-message-blocks">
            {a2uiBlocks.map((block, index) => (
                <A2UIRenderer
                    key={index}
                    surface={block.surface}
                    onAction={onAction}
                />
            ))}
        </div>
    );
};

export default A2UIRenderer;

import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

/**
 * Enhanced Modal with fixed Header and Footer sections
 * to ensure action buttons are always visible.
 */
export default function Modal({ isOpen, onClose, title, children, footer, maxWidth = 'max-w-lg' }) {
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => { document.body.style.overflow = 'unset'; };
    }, [isOpen]);

    if (!isOpen) return null;

    const modalContent = (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 sm:p-6 md:p-10">
            {/* Backdrop */}
            <div 
                className="absolute inset-0 bg-[#0B0E11]/80 backdrop-blur-md animate-in fade-in duration-300"
                onClick={onClose}
            />
            
            {/* Main Modal Container */}
            <div className={`
                relative w-full ${maxWidth} bg-[#131722] border border-white/10 rounded-[32px] 
                shadow-[0_32px_64px_-12px_rgba(0,0,0,0.8)] flex flex-col 
                max-h-[90vh] overflow-hidden animate-in zoom-in-95 fade-in duration-300
            `}>
                {/* Fixed Header */}
                <div className="flex items-center justify-between p-8 border-b border-white/5 flex-shrink-0">
                    <h2 className="text-xl font-black text-white tracking-tight">{title}</h2>
                    <button 
                        onClick={onClose}
                        className="w-10 h-10 rounded-full flex items-center justify-center text-slate-500 hover:text-white hover:bg-white/5 transition-all outline-none"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>
                
                {/* Scrollable Content (Takes rest of space) */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-8 pt-6">
                    <div className="animate-in fade-in slide-in-from-top-4 duration-500 pb-4">
                        {children}
                    </div>
                </div>

                {/* Fixed Footer (Stays at bottom) */}
                {footer && (
                    <div className="p-6 pb-8 px-8 border-t border-white/5 bg-black/20 flex-shrink-0">
                        {footer}
                    </div>
                )}
            </div>
        </div>
    );

    return createPortal(modalContent, document.body);
}

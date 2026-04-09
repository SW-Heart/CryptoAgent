import React, { useEffect, useRef, memo } from 'react';

const TradingViewWidget = ({ 
  symbol,
  watchlist,
  theme = "dark",
  locale = "zh_CN",
  timezone = "Asia/Shanghai",
  studies = ["Volume@tv-basicstudies", "MACD@tv-basicstudies"],
  ...customProps 
}) => {
  const containerRef = useRef(null);
  const widgetRef = useRef(null);

  // Stringify the arrays to use as dependency triggers to avoid unnecessary re-mounts on object reference changes
  const watchlistStr = JSON.stringify(watchlist || []);
  const studiesStr = JSON.stringify(studies || []);

  useEffect(() => {
    let script = document.getElementById('tradingview-widget-script');
    
    const initWidget = () => {
      if (typeof window.TradingView === 'undefined') return;
      if (!containerRef.current) return;

      // Ensure proper cleanup of previous instance if it exists
      if (widgetRef.current && widgetRef.current.remove) {
        try {
          widgetRef.current.remove();
        } catch (e) {
          // Ignore error to make it robust
        }
      }

      containerRef.current.innerHTML = '';
      const containerId = `tv_widget_${Math.random().toString(36).substring(2, 9)}`;
      containerRef.current.id = containerId;

      const widgetConfig = {
        autosize: true,
        symbol: symbol,
        interval: '1D',
        timezone: timezone,
        theme: theme,
        style: '1',
        locale: locale,
        enable_publishing: false,
        backgroundColor: '#0B0E11',
        gridColor: '#1f2937',
        hide_top_toolbar: false,
        hide_side_toolbar: false,
        hide_legend: false,
        save_image: false,
        allow_symbol_change: true,
        container_id: containerId,
        withdateranges: true,
        details: true,
        hotlist: true,
        calendar: false,
        watchlist: JSON.parse(watchlistStr),
        studies: JSON.parse(studiesStr),
        ...customProps
      };

      widgetRef.current = new window.TradingView.widget(widgetConfig);
    };

    if (!script) {
      script = document.createElement('script');
      script.id = 'tradingview-widget-script';
      script.src = 'https://s3.tradingview.com/tv.js';
      script.async = true;
      script.onload = initWidget;
      document.head.appendChild(script);
    } else {
      initWidget();
    }

    return () => {
      // This is the critical cleanup phase that prevents 'parentElement is null' errors
      // inside tv.js on component unmount
      if (widgetRef.current && widgetRef.current.remove) {
        try {
          widgetRef.current.remove();
          widgetRef.current = null;
        } catch (e) {
          console.warn("TV Widget clean up error:", e);
        }
      }
      if (containerRef.current) {
        containerRef.current.innerHTML = ''; 
      }
    };
  }, [symbol, watchlistStr, studiesStr, theme, locale, timezone]);

  return (
    <div ref={containerRef} className="w-full h-full absolute inset-0" />
  );
}

export default memo(TradingViewWidget);

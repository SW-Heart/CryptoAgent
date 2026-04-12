import React from 'react';
import { useTranslation } from 'react-i18next';
import CoinButton from './CoinButton';

const CoinButtonBar = React.memo(({ coins, onCoinClick }) => {
    const { t } = useTranslation();

    if (!coins || coins.length === 0) return null;

    return (
        <div className="mt-4 pt-4">
            <div className="flex items-center gap-2 mb-2">
                <span className="text-xs text-slate-400 font-medium">📈 {t('tool.viewChart')}</span>
            </div>
            <div className="flex flex-wrap gap-2">
                {coins.map(coin => (
                    <CoinButton key={coin} coin={coin} onClick={onCoinClick} />
                ))}
            </div>
        </div>
    );
});

export default CoinButtonBar;

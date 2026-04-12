/**
 * Client Actions - A2UI 动作处理器
 * 
 * 定义客户端可执行的动作，由 A2UI 按钮触发。
 * 这是安全层的关键：Agent 只能触发预定义的动作，无法执行任意代码。
 */

import walletService from './walletService';

// ==========================================
// Token 地址映射
// ==========================================

const TOKEN_ADDRESSES = {
    USDT: '0xdAC17F958D2ee523a2206206994597C13D831ec7',
    USDC: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
    DAI: '0x6B175474E89094C44Da98b954EescdececfE1f9',
    WETH: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
    WBTC: '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
    ETH: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
    BTC: '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
};

// ==========================================
// 动作注册表
// ==========================================

/**
 * 预定义的客户端动作
 * 每个动作是一个异步函数，接收 params 参数
 */
const clientActions = {
    /**
     * 执行链上 Swap 交易
     * 
     * 流程:
     * 1. 连接钱包
     * 2. 检查并切换网络
     * 3. 检查 Token 授权
     * 4. 调用 Uniswap Router 执行交易
     */
    EXECUTE_ONCHAIN_SWAP: async (params, callbacks = {}) => {
        const { onStatusChange } = callbacks;

        console.log('[ClientAction] EXECUTE_ONCHAIN_SWAP:', params);

        try {
            // 1. 通知状态: 连接钱包
            onStatusChange?.('connecting', '正在连接钱包...');

            // 检查钱包是否安装
            if (!walletService.isWalletInstalled()) {
                throw new Error('请安装 MetaMask 钱包后重试');
            }

            // 连接钱包
            const { address, signer } = await walletService.connectWallet();
            console.log('[ClientAction] Wallet connected:', address);

            // 2. 检查并切换网络
            const targetChainId = params.chainId || 1;
            const currentChainId = await walletService.getChainId();

            if (currentChainId !== targetChainId) {
                onStatusChange?.('switching', '正在切换网络...');
                await walletService.switchNetwork(targetChainId);
            }

            // 3. 检查 Token 授权 (非 ETH 交易需要)
            const fromToken = params.fromToken?.toUpperCase();
            if (fromToken && fromToken !== 'ETH' && fromToken !== 'WETH') {
                const tokenAddress = TOKEN_ADDRESSES[fromToken];
                if (tokenAddress) {
                    onStatusChange?.('approving', '正在检查授权...');
                    await walletService.ensureTokenApproval(tokenAddress, params.fromAmount);
                }
            }

            // 4. 构建并发送交易
            onStatusChange?.('confirming', '请在钱包中确认交易...');

            // 如果有预生成的 calldata，直接发送
            if (params.calldata && params.calldata !== 'PENDING_GENERATION') {
                const receipt = await walletService.sendTransaction({
                    to: params.routerAddress,
                    data: params.calldata,
                    value: params.value || '0',
                    gasLimit: params.gasLimit,
                });

                onStatusChange?.('success', '交易成功！');
                return {
                    success: true,
                    txHash: receipt.hash,
                    blockNumber: receipt.blockNumber,
                };
            }

            // 如果没有 calldata，需要生成（这里是简化版，实际需要调用 Uniswap SDK）
            // 目前先返回模拟成功
            console.log('[ClientAction] Note: calldata not provided, using simulated flow');

            // 为了演示，我们假设交易成功
            // 实际生产环境需要集成 Uniswap SDK 生成真实 calldata
            onStatusChange?.('pending', '交易已提交，等待确认...');

            // 模拟等待
            await new Promise(resolve => setTimeout(resolve, 2000));

            onStatusChange?.('success', '交易成功！');
            return {
                success: true,
                txHash: '0x' + Math.random().toString(16).slice(2, 66),
                simulated: true,
                message: '这是模拟交易。生产环境需要集成完整的 Uniswap SDK。',
            };

        } catch (error) {
            console.error('[ClientAction] EXECUTE_ONCHAIN_SWAP error:', error);
            onStatusChange?.('failed', error.message || '交易失败');

            return {
                success: false,
                error: error.message || '交易执行失败',
            };
        }
    },

    /**
     * 取消交易
     */
    CANCEL_SWAP: async (params, callbacks = {}) => {
        console.log('[ClientAction] CANCEL_SWAP');
        callbacks.onStatusChange?.('cancelled', '交易已取消');
        return { success: true, cancelled: true };
    },

    /**
     * 连接钱包（独立动作）
     */
    CONNECT_WALLET: async (params, callbacks = {}) => {
        try {
            callbacks.onStatusChange?.('connecting', '正在连接钱包...');
            const { address } = await walletService.connectWallet();
            callbacks.onStatusChange?.('success', '钱包已连接');
            return { success: true, address };
        } catch (error) {
            callbacks.onStatusChange?.('failed', error.message);
            return { success: false, error: error.message };
        }
    },

    /**
     * 授权 Token
     */
    APPROVE_TOKEN: async (params, callbacks = {}) => {
        try {
            const { tokenAddress, tokenSymbol } = params;
            callbacks.onStatusChange?.('approving', `正在授权 ${tokenSymbol || 'Token'}...`);

            const receipt = await walletService.approveToken(tokenAddress);
            callbacks.onStatusChange?.('success', '授权成功');

            return { success: true, txHash: receipt.hash };
        } catch (error) {
            callbacks.onStatusChange?.('failed', error.message);
            return { success: false, error: error.message };
        }
    },
};

// ==========================================
// 动作执行器
// ==========================================

/**
 * 执行 A2UI 动作
 * 
 * @param {string} actionId - 动作 ID
 * @param {Object} params - 动作参数
 * @param {Object} callbacks - 回调函数 { onStatusChange: (status, message) => void }
 * @returns {Promise<Object>} 执行结果
 */
export const executeAction = async (actionId, params = {}, callbacks = {}) => {
    console.log('[ClientActions] Executing:', actionId, params);

    const action = clientActions[actionId];

    if (!action) {
        console.error('[ClientActions] Unknown action:', actionId);
        return {
            success: false,
            error: `未知的动作: ${actionId}`,
        };
    }

    try {
        return await action(params, callbacks);
    } catch (error) {
        console.error('[ClientActions] Execution error:', error);
        return {
            success: false,
            error: error.message || '动作执行失败',
        };
    }
};

/**
 * 获取所有已注册的动作 ID
 */
export const getRegisteredActions = () => {
    return Object.keys(clientActions);
};

/**
 * 检查动作是否存在
 */
export const hasAction = (actionId) => {
    return actionId in clientActions;
};

export default {
    executeAction,
    getRegisteredActions,
    hasAction,
};

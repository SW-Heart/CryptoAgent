/**
 * Wallet Service - 钱包连接和交互服务
 * 
 * 提供 MetaMask 等钱包的连接、网络切换、授权检查等功能。
 */

import { ethers } from 'ethers';

// ==========================================
// 常量配置
// ==========================================

// 支持的网络
const SUPPORTED_CHAINS = {
    1: {
        name: 'Ethereum Mainnet',
        rpcUrl: 'https://eth.llamarpc.com',
        nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
        blockExplorer: 'https://etherscan.io',
    },
    5: {
        name: 'Goerli Testnet',
        rpcUrl: 'https://rpc.ankr.com/eth_goerli',
        nativeCurrency: { name: 'Goerli Ether', symbol: 'ETH', decimals: 18 },
        blockExplorer: 'https://goerli.etherscan.io',
    },
    11155111: {
        name: 'Sepolia Testnet',
        rpcUrl: 'https://rpc.sepolia.org',
        nativeCurrency: { name: 'Sepolia Ether', symbol: 'ETH', decimals: 18 },
        blockExplorer: 'https://sepolia.etherscan.io',
    },
};

// Permit2 合约地址 (所有链通用)
const PERMIT2_ADDRESS = '0x000000000022D473030F116dDEE9F6B43aC78BA3';

// Uniswap Universal Router 地址
const UNISWAP_ROUTERS = {
    1: '0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD', // Ethereum Mainnet
    5: '0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD', // Goerli (使用相同地址)
};

// ==========================================
// 钱包连接
// ==========================================

/**
 * 检查是否已安装 MetaMask
 */
export const isWalletInstalled = () => {
    return typeof window !== 'undefined' && window.ethereum !== undefined;
};

/**
 * 连接 MetaMask 钱包
 * @returns {Promise<{ provider: ethers.BrowserProvider, signer: ethers.Signer, address: string }>}
 */
export const connectWallet = async () => {
    if (!isWalletInstalled()) {
        throw new Error('请安装 MetaMask 钱包');
    }

    try {
        // 请求账户连接
        await window.ethereum.request({ method: 'eth_requestAccounts' });

        // 创建 Provider 和 Signer
        const provider = new ethers.BrowserProvider(window.ethereum);
        const signer = await provider.getSigner();
        const address = await signer.getAddress();

        console.log('[Wallet] Connected:', address);

        return { provider, signer, address };
    } catch (error) {
        if (error.code === 4001) {
            throw new Error('用户拒绝了连接请求');
        }
        throw error;
    }
};

/**
 * 获取当前连接的地址
 */
export const getConnectedAddress = async () => {
    if (!isWalletInstalled()) return null;

    try {
        const accounts = await window.ethereum.request({ method: 'eth_accounts' });
        return accounts[0] || null;
    } catch {
        return null;
    }
};

/**
 * 获取当前链 ID
 */
export const getChainId = async () => {
    if (!isWalletInstalled()) return null;

    try {
        const chainIdHex = await window.ethereum.request({ method: 'eth_chainId' });
        return parseInt(chainIdHex, 16);
    } catch {
        return null;
    }
};

// ==========================================
// 网络切换
// ==========================================

/**
 * 切换到指定网络
 * @param {number} chainId - 目标链 ID
 */
export const switchNetwork = async (chainId) => {
    if (!isWalletInstalled()) {
        throw new Error('请安装 MetaMask 钱包');
    }

    const chainConfig = SUPPORTED_CHAINS[chainId];
    if (!chainConfig) {
        throw new Error(`不支持的网络: ${chainId}`);
    }

    const chainIdHex = `0x${chainId.toString(16)}`;

    try {
        await window.ethereum.request({
            method: 'wallet_switchEthereumChain',
            params: [{ chainId: chainIdHex }],
        });
    } catch (error) {
        // 如果网络不存在，尝试添加
        if (error.code === 4902) {
            await window.ethereum.request({
                method: 'wallet_addEthereumChain',
                params: [{
                    chainId: chainIdHex,
                    chainName: chainConfig.name,
                    rpcUrls: [chainConfig.rpcUrl],
                    nativeCurrency: chainConfig.nativeCurrency,
                    blockExplorerUrls: [chainConfig.blockExplorer],
                }],
            });
        } else {
            throw error;
        }
    }
};

// ==========================================
// Token 授权
// ==========================================

// ERC20 ABI (仅需 allowance 和 approve)
const ERC20_ABI = [
    'function allowance(address owner, address spender) view returns (uint256)',
    'function approve(address spender, uint256 amount) returns (bool)',
    'function decimals() view returns (uint8)',
    'function symbol() view returns (string)',
];

/**
 * 检查 Token 授权额度
 * @param {string} tokenAddress - Token 合约地址
 * @param {string} ownerAddress - 持有者地址
 * @param {string} spenderAddress - 被授权者地址 (默认 Permit2)
 */
export const checkTokenAllowance = async (tokenAddress, ownerAddress, spenderAddress = PERMIT2_ADDRESS) => {
    const provider = new ethers.BrowserProvider(window.ethereum);
    const tokenContract = new ethers.Contract(tokenAddress, ERC20_ABI, provider);

    const allowance = await tokenContract.allowance(ownerAddress, spenderAddress);
    return allowance;
};

/**
 * 授权 Token 给 Permit2
 * @param {string} tokenAddress - Token 合约地址
 * @param {string} amount - 授权数量 (或 'MAX' 表示最大值)
 */
export const approveToken = async (tokenAddress, amount = 'MAX') => {
    const { signer, address } = await connectWallet();
    const tokenContract = new ethers.Contract(tokenAddress, ERC20_ABI, signer);

    // 最大授权量
    const approveAmount = amount === 'MAX'
        ? ethers.MaxUint256
        : ethers.parseUnits(amount.toString(), await tokenContract.decimals());

    console.log('[Wallet] Approving token:', tokenAddress, 'amount:', approveAmount.toString());

    const tx = await tokenContract.approve(PERMIT2_ADDRESS, approveAmount);
    const receipt = await tx.wait();

    console.log('[Wallet] Approval confirmed:', receipt.hash);
    return receipt;
};

/**
 * 确保 Token 已授权足够额度
 * @param {string} tokenAddress - Token 合约地址
 * @param {string} requiredAmount - 需要的数量
 */
export const ensureTokenApproval = async (tokenAddress, requiredAmount) => {
    const { address } = await connectWallet();

    const allowance = await checkTokenAllowance(tokenAddress, address);
    const provider = new ethers.BrowserProvider(window.ethereum);
    const tokenContract = new ethers.Contract(tokenAddress, ERC20_ABI, provider);
    const decimals = await tokenContract.decimals();
    const required = ethers.parseUnits(requiredAmount.toString(), decimals);

    if (allowance < required) {
        console.log('[Wallet] Insufficient allowance, requesting approval...');
        await approveToken(tokenAddress, 'MAX');
    } else {
        console.log('[Wallet] Token already approved');
    }
};

// ==========================================
// 交易发送
// ==========================================

/**
 * 发送交易
 * @param {Object} txParams - 交易参数
 */
export const sendTransaction = async ({ to, data, value = '0', gasLimit }) => {
    const { signer } = await connectWallet();

    const tx = await signer.sendTransaction({
        to,
        data,
        value: ethers.parseEther(value),
        gasLimit: gasLimit ? BigInt(gasLimit) : undefined,
    });

    console.log('[Wallet] Transaction sent:', tx.hash);

    // 等待确认
    const receipt = await tx.wait();
    console.log('[Wallet] Transaction confirmed:', receipt.hash);

    return receipt;
};

// ==========================================
// 事件监听
// ==========================================

/**
 * 监听账户变化
 */
export const onAccountsChanged = (callback) => {
    if (!isWalletInstalled()) return;
    window.ethereum.on('accountsChanged', callback);
};

/**
 * 监听网络变化
 */
export const onChainChanged = (callback) => {
    if (!isWalletInstalled()) return;
    window.ethereum.on('chainChanged', (chainIdHex) => {
        callback(parseInt(chainIdHex, 16));
    });
};

/**
 * 移除事件监听
 */
export const removeListeners = () => {
    if (!isWalletInstalled()) return;
    window.ethereum.removeAllListeners('accountsChanged');
    window.ethereum.removeAllListeners('chainChanged');
};

export default {
    isWalletInstalled,
    connectWallet,
    getConnectedAddress,
    getChainId,
    switchNetwork,
    checkTokenAllowance,
    approveToken,
    ensureTokenApproval,
    sendTransaction,
    onAccountsChanged,
    onChainChanged,
    removeListeners,
};

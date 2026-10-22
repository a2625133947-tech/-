import i18n from '@/i18n';

const investorNamesZh: Record<string, string> = {
  duan_yongping: '段永平',
  deng_xiaofeng: '邓晓峰',
  feng_liu: '冯柳',
  fu_pengbo: '傅鹏博',
  zhu_shaoxing: '朱少醒',
  zhang_kun: '张坤',
  liu_yanchun: '刘彦春',
  xie_zhiyu: '谢治宇',
  dong_chengfei: '董承非',
  wang_yawei: '王亚伟',
  chen_guangming: '陈光明',
  lin_yuan: '林园',
};

const investorNamesEn: Record<string, string> = {
  duan_yongping: 'Duan Yongping',
  deng_xiaofeng: 'Deng Xiaofeng',
  feng_liu: 'Feng Liu',
  fu_pengbo: 'Fu Pengbo',
  zhu_shaoxing: 'Zhu Shaoxing',
  zhang_kun: 'Zhang Kun',
  liu_yanchun: 'Liu Yanchun',
  xie_zhiyu: 'Xie Zhiyu',
  dong_chengfei: 'Dong Chengfei',
  wang_yawei: 'Wang Yawei',
  chen_guangming: 'Chen Guangming',
  lin_yuan: 'Lin Yuan',
};

export function getInvestorDisplayName(agentId: string): string | undefined {
  const key = agentId.replace(/_[a-z0-9]{6}$/, '').replace(/_agent$/, '');
  const isEn = i18n.language === 'en-US';
  return isEn 
    ? (investorNamesEn[key] || investorNamesZh[key]) 
    : (investorNamesZh[key] || investorNamesEn[key]);
}

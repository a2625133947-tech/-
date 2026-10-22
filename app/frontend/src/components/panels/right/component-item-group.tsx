import ComponentItem from '@/components/panels/right/component-item';
import { AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { useFlowContext } from '@/contexts/flow-context';
import { ComponentGroup } from '@/data/sidebar-components';
import { useTranslation } from 'react-i18next';

interface ComponentItemGroupProps {
  group: ComponentGroup;
  activeItem: string | null;
}

export function ComponentItemGroup({ 
  group, 
  activeItem
}: ComponentItemGroupProps) {
  const { t } = useTranslation();
  const { name, icon: Icon, iconColor, items } = group;
  const { addComponentToFlow } = useFlowContext();

  const handleItemClick = async (componentName: string) => {
    try {
      await addComponentToFlow(componentName);
    } catch (error) {
      console.error('Failed to add component to flow:', error);
    }
  };

  const getLocalizedGroupName = (grpName: string) => {
    switch (grpName) {
      case 'Start Nodes':
        return t('flow.start_nodes');
      case 'Analysts':
        return t('flow.analysts');
      case 'Swarms':
        return t('flow.swarms');
      case 'End Nodes':
        return t('flow.end_nodes');
      default:
        return grpName;
    }
  };

  const getLocalizedItemLabel = (itemName: string) => {
    switch (itemName) {
      case 'Portfolio Input':
        return t('flow.portfolio_input');
      case 'Stock Input':
        return t('flow.stock_input');
      case 'Portfolio Manager':
        return t('flow.portfolio_manager');
      case 'Investment Report':
        return t('flow.investment_report');
      case 'JSON Output':
        return t('flow.json_output');
      case '数据分析':
        return t('flow.data_analysis');
      case 'A股成长投资':
        return t('flow.a_share_growth');
      case 'A股价值投资':
        return t('flow.a_share_value');
      default:
        return itemName;
    }
  };
  
  return (
    <AccordionItem key={name} value={name} className="border-none">
      <AccordionTrigger className="px-4 py-2 text-sm hover-bg hover:no-underline">
        <div className="flex items-center gap-2">
          <Icon size={16} className={iconColor} />
          <span className="capitalize">{getLocalizedGroupName(name)}</span>
        </div>
      </AccordionTrigger>
      <AccordionContent className="px-4">
        <div className="space-y-1">
          {items.map((item) => (
            <ComponentItem 
              key={item.name}
              icon={item.icon} 
              label={getLocalizedItemLabel(item.name)} 
              isActive={activeItem === item.name}
              onClick={() => handleItemClick(item.name)}
            />
          ))}
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}

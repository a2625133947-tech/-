import { cn } from '@/lib/utils';
import { Cloud, Server } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CloudModels } from './models/cloud';
import { OllamaSettings } from './models/ollama';

interface ModelsProps {
  className?: string;
}

interface ModelSection {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  component: React.ComponentType;
}

export function Models({ className }: ModelsProps) {
  const { t } = useTranslation();
  const [selectedSection, setSelectedSection] = useState('cloud');

  const modelSections: ModelSection[] = [
    {
      id: 'cloud',
      label: t('settings.models.cloud'),
      icon: Cloud,
      description: t('settings.models.cloud_desc'),
      component: CloudModels,
    },
    {
      id: 'local',
      label: t('settings.models.ollama'),
      icon: Server,
      description: t('settings.models.ollama_desc'),
      component: OllamaSettings,
    },
  ];

  const renderContent = () => {
    const section = modelSections.find(s => s.id === selectedSection);
    if (!section) return null;
    
    const Component = section.component;
    return <Component />;
  };

  return (
    <div className={cn("space-y-6", className)}>
      <div>
        <h2 className="text-xl font-semibold text-primary mb-2">{t('settings.models.title')}</h2>
        <p className="text-sm text-muted-foreground">
          {t('settings.models.desc')}
        </p>
      </div>

      {/* Model Type Navigation */}
      <div className="flex space-x-1 bg-muted p-1 rounded-lg">
        {modelSections.map((section) => {
          const Icon = section.icon;
          const isSelected = selectedSection === section.id;
          
          return (
            <button
              key={section.id}
              onClick={() => setSelectedSection(section.id)}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-colors",
                isSelected 
                  ? "active-bg text-emerald-400 shadow-sm" 
                  : "text-primary hover:text-primary hover-bg"
              )}
            >
              <Icon className="h-4 w-4" />
              {section.label}
            </button>
          );
        })}
      </div>

      {/* Content Area */}
      <div className="mt-6">
        {renderContent()}
      </div>
    </div>
  );
}

import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { useToastManager } from '@/hooks/use-toast-manager';
import { flowService } from '@/services/flow-service';
import { Flow } from '@/types/flow';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface FlowCreateDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onFlowCreated: (flow: Flow) => void;
}

export function FlowCreateDialog({ isOpen, onClose, onFlowCreated }: FlowCreateDialogProps) {
  const { t } = useTranslation();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { success, error } = useToastManager();

  // Reset form when dialog opens
  useEffect(() => {
    if (isOpen) {
      setName('');
      setDescription('');
    }
  }, [isOpen]);

  const handleCreate = async () => {
    if (!name.trim()) {
      error('Flow name is required');
      return;
    }

    setIsLoading(true);
    try {
      const newFlow = await flowService.createFlow({
        name: name.trim(),
        description: description.trim() || undefined,
        nodes: [],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      });
      
      success(`"${newFlow.name}" created!`);
      onFlowCreated(newFlow);
      onClose();
    } catch (err) {
      console.error('Failed to create flow:', err);
      error('Failed to create flow');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    setName('');
    setDescription('');
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Handle Cmd+Enter (Mac) or Ctrl+Enter (Windows/Linux)
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (name.trim()) {
        handleCreate();
      }
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>{t('flow.create_new_flow')}</DialogTitle>
          <DialogDescription>
            {t('flow.new_flow_desc')}
          </DialogDescription>
        </DialogHeader>
        
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label htmlFor="create-name" className="text-sm font-medium">
              {t('common.name')}
            </label>
            <Input
              id="create-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('flow.new_flow_name')}
              className="col-span-3"
              autoFocus
            />
          </div>
          
          <div className="grid gap-2">
            <label htmlFor="create-description" className="text-sm font-medium">
              {t('common.description')}
            </label>
            <Input
              id="create-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('flow.new_flow_desc')}
              className="col-span-3"
            />
          </div>
        </div>
        
        <DialogFooter>
          <Button variant="outline" onClick={handleCancel}>
            {t('common.cancel')}
          </Button>
          <Button 
            onClick={handleCreate} 
            disabled={isLoading || !name.trim()}
          >
            {isLoading ? t('common.loading') : t('common.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
} 
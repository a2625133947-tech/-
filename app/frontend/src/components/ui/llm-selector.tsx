import { ChevronsUpDown } from "lucide-react"
import * as React from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { modelIdentity, type LanguageModel } from "@/data/models"
import { cn } from "@/lib/utils"
import { useTranslation } from "react-i18next"

interface ModelSelectorProps {
  models: LanguageModel[];
  value: LanguageModel | null;
  onChange: (item: LanguageModel | null) => void;
  placeholder?: string;
}

export function ModelSelector({ 
  models, 
  value, 
  onChange, 
  placeholder
}: ModelSelectorProps) {
  const { t } = useTranslation();
  const [open, setOpen] = React.useState(false)
  const available = value && models.some(model => modelIdentity(model) === modelIdentity(value))
  const displayPlaceholder = placeholder || t('nodes.stock_analyzer.select_model');

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between bg-node border border-border"
        >
          <span className="text-subtitle">
            {value ? `${value.display_name}${available ? '' : ' (no longer listed)'}` : displayPlaceholder}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-full min-w-[350px] p-0 bg-node border border-border shadow-lg">
        <Command className="bg-node">
          <CommandInput placeholder={t('common.search')} className="h-9 bg-node" />
          <CommandList className="bg-node">
            <CommandEmpty>{t('common.na')}</CommandEmpty>
            <CommandGroup>
              {models.map((model) => (
                <CommandItem
                  key={modelIdentity(model)}
                  value={`${model.provider} ${model.model_name} ${model.display_name}`}
                  className={cn(
                    "cursor-pointer bg-node hover:bg-accent",
                    value && modelIdentity(value) === modelIdentity(model) && "bg-blue-600/10 border-l-2 border-blue-500/50"
                  )}
                  onSelect={() => {
                    if (value && modelIdentity(value) === modelIdentity(model)) {
                      onChange(null);
                    } else {
                      onChange(model);
                    }
                    setOpen(false);
                  }}
                >
                  <div className="flex items-center justify-between w-full">
                    <div className="flex flex-col items-start min-w-0 flex-1">
                      <span className="text-title">{model.display_name}</span>
                      <span className="text-xs text-muted-foreground font-mono">{model.model_name}</span>
                      {model.compatibility === 'unverified' && <span className="text-xs text-amber-500">{t('settings.models.compatibility_unverified')}</span>}
                    </div>
                    <Badge className="text-xs text-primary bg-primary/10 border-primary/30 hover:bg-primary/20 hover:border-primary/50">
                      {model.provider}
                    </Badge>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

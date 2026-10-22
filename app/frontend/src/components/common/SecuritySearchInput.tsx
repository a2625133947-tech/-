import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Loader2, AlertCircle, Check, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { securityApi, SecurityItem } from '@/services/security-api';
import { useTranslation } from 'react-i18next';

export interface SecuritySearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSelectSecurity?: (sec: SecurityItem) => void;
  placeholder?: string;
  className?: string;
  id?: string;
  multi?: boolean;
  disabled?: boolean;
}

const RECENT_STORAGE_KEY = 'ahf_recent_securities';

export const SecuritySearchInput: React.FC<SecuritySearchInputProps> = ({
  value,
  onChange,
  onSelectSecurity,
  placeholder,
  className = '',
  id,
  multi = false,
  disabled = false,
}) => {
  const { t } = useTranslation();
  const [inputValue, setInputValue] = useState<string>(value || '');
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [selectedSecurity, setSelectedSecurity] = useState<SecurityItem | null>(null);
  const [results, setResults] = useState<SecurityItem[]>([]);
  const [totalMatches, setTotalMatches] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const [recentList, setRecentList] = useState<SecurityItem[]>([]);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLLIElement | null)[]>([]);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const searchGenerationRef = useRef<number>(0);
  const isCommittedRef = useRef<boolean>(false);

  // Isolate wheel events at native DOM level to prevent React Flow canvas zoom/pan
  // while preserving native smooth scrolling within the dropdown.
  useEffect(() => {
    const el = dropdownRef.current;
    if (!el || !isOpen) return;

    const handleWheel = (e: WheelEvent) => {
      // Allow browser native scroll inside dropdown, stop bubbling to React Flow canvas
      e.stopPropagation();
    };

    // Capture phase ensures event propagation stops before any outer listeners run
    el.addEventListener('wheel', handleWheel, { capture: true, passive: true });
    el.addEventListener('wheel', handleWheel, { capture: false, passive: true });
    return () => {
      el.removeEventListener('wheel', handleWheel, { capture: true });
      el.removeEventListener('wheel', handleWheel, { capture: false });
    };
  }, [isOpen]);

  // Scroll active item into view during keyboard navigation
  useEffect(() => {
    if (activeIndex >= 0 && itemRefs.current[activeIndex]) {
      itemRefs.current[activeIndex]?.scrollIntoView({
        block: 'nearest',
      });
    }
  }, [activeIndex]);

  // Sync external value changes
  useEffect(() => {
    setInputValue(value || '');
  }, [value]);

  // Load recent securities from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(RECENT_STORAGE_KEY);
      if (stored) {
        setRecentList(JSON.parse(stored));
      }
    } catch {
      // Ignore storage errors
    }
  }, []);

  const saveRecent = (sec: SecurityItem) => {
    try {
      const updated = [sec, ...recentList.filter((s) => s.symbol !== sec.symbol)].slice(0, 8);
      setRecentList(updated);
      localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(updated));
    } catch {
      // Ignore storage errors
    }
  };

  // Extract current search token for multi-input mode
  const getCurrentSearchToken = useCallback((text: string): string => {
    if (!multi) return text.trim();
    const parts = text.split(',');
    return parts[parts.length - 1].trim();
  }, [multi]);

  const performSearch = useCallback(async (rawQuery: string) => {
    const q = getCurrentSearchToken(rawQuery);
    const thisGen = ++searchGenerationRef.current;

    setIsLoading(true);
    setErrorMsg(null);

    try {
      const resp = await securityApi.search(q, 10);
      // If user has committed a selection or a newer search was initiated, discard results
      if (thisGen !== searchGenerationRef.current || isCommittedRef.current) {
        return;
      }
      setResults(resp.results || []);
      setTotalMatches(resp.total_matches || 0);
      setActiveIndex(resp.results.length > 0 ? 0 : -1);
    } catch (err: any) {
      if (thisGen !== searchGenerationRef.current || isCommittedRef.current) {
        return;
      }
      console.warn('Security search warning:', err);
      setErrorMsg(t('security.search_unavailable', { defaultValue: '证券搜索暂时不可用，可直接输入代码' }));
      setResults([]);
    } finally {
      if (thisGen === searchGenerationRef.current && !isCommittedRef.current) {
        setIsLoading(false);
      }
    }
  }, [getCurrentSearchToken, t]);

  // Unified commit selection action for both Mouse click and Keyboard Enter
  const commitSelection = useCallback((sec: SecurityItem) => {
    // 1. Invalidate any in-flight searches & cancel pending debounce timer
    searchGenerationRef.current++;
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    // 2. Mark state machine as COMMITTED (State B)
    isCommittedRef.current = true;
    setSelectedSecurity(sec);
    saveRecent(sec);

    // 3. Compute new input value
    let finalValue = sec.canonical_symbol;
    if (multi) {
      const parts = inputValue.split(',').map((p) => p.trim());
      parts[parts.length - 1] = sec.canonical_symbol;
      finalValue = parts.filter(Boolean).join(',');
    }

    setInputValue(finalValue);
    onChange(finalValue);
    onSelectSecurity?.(sec);

    // 4. Immediately close dropdown and clear candidate results
    setIsOpen(false);
    setResults([]);
    setActiveIndex(-1);
    setIsLoading(false);

    // 5. Retain input focus without re-opening dropdown
    inputRef.current?.focus();
  }, [inputValue, multi, onChange, onSelectSecurity]);

  // Debounced input change handler - switches to State C / State A (Searching)
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVal = e.target.value;
    // User is editing: exit committed state
    isCommittedRef.current = false;
    setSelectedSecurity(null);
    setInputValue(newVal);
    onChange(newVal); // Let parent receive raw edits immediately

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    const token = getCurrentSearchToken(newVal);
    if (!token && !multi) {
      // Empty input: show popular/recent
      searchGenerationRef.current++;
      setResults(recentList.length > 0 ? recentList : []);
      setActiveIndex(-1);
      setIsOpen(true);
      return;
    }

    if (!token && multi) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    debounceTimerRef.current = setTimeout(() => {
      performSearch(newVal);
      setIsOpen(true);
    }, 200);
  };

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        isCommittedRef.current = false;
        setIsOpen(true);
        performSearch(inputValue);
        e.preventDefault();
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((prev) => (prev < results.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((prev) => (prev > 0 ? prev - 1 : results.length - 1));
    } else if (e.key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < results.length) {
        e.preventDefault();
        commitSelection(results[activeIndex]);
      } else {
        // Direct enter without active item: try resolve then commit or close
        const token = getCurrentSearchToken(inputValue);
        if (token) {
          securityApi.resolve(token).then((res) => {
            if (res.resolved && res.security) {
              commitSelection(res.security);
            }
          }).catch(() => {});
        }
        setIsOpen(false);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      e.preventDefault();
    }
  };

  // Click outside listener
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const getExchangeBadge = (exchange: string, board: string) => {
    if (board === '科创板') {
      return <Badge className="bg-purple-500/15 text-purple-600 dark:text-purple-400 border-purple-500/30 text-[10px] px-1 py-0">科创板</Badge>;
    }
    if (board === '创业板') {
      return <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 text-[10px] px-1 py-0">创业板</Badge>;
    }
    if (board === '北交所') {
      return <Badge className="bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30 text-[10px] px-1 py-0">北交所</Badge>;
    }
    if (exchange === 'SSE') {
      return <Badge className="bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30 text-[10px] px-1 py-0">上交所</Badge>;
    }
    return <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px] px-1 py-0">深交所</Badge>;
  };

  return (
    <div ref={containerRef} className="relative w-full nowheel nodrag nopan">
      <div className="relative flex items-center">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
        <input
          ref={inputRef}
          id={id}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onFocus={() => {
            // If already committed with selection, do not re-open on focus
            if (isCommittedRef.current || selectedSecurity) {
              return;
            }
            const token = getCurrentSearchToken(inputValue);
            if (!token && recentList.length > 0) {
              setResults(recentList);
              setIsOpen(true);
            } else if (token) {
              performSearch(inputValue);
              setIsOpen(true);
            }
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          title={selectedSecurity ? `${selectedSecurity.name} (${selectedSecurity.symbol})` : undefined}
          data-selected-symbol={selectedSecurity?.symbol}
          placeholder={placeholder || t('security.search_placeholder', { defaultValue: '输入代码、公司名或拼音 (如 600519、茅台、gzmt)' })}
          className={`w-full bg-background border border-border rounded-md pl-8 pr-7 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors nodrag nowheel nopan ${className}`}
          autoComplete="off"
          spellCheck="false"
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
        />
        {isLoading ? (
          <Loader2 size={13} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground animate-spin pointer-events-none" />
        ) : inputValue ? (
          <button
            type="button"
            onClick={() => {
              isCommittedRef.current = false;
              setSelectedSecurity(null);
              setInputValue('');
              onChange('');
              setIsOpen(false);
              setResults([]);
              inputRef.current?.focus();
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5 rounded"
          >
            <X size={12} />
          </button>
        ) : null}
      </div>

      {/* Autocomplete Dropdown List */}
      {isOpen && (
        <div
          ref={dropdownRef}
          onWheelCapture={(e) => {
            e.stopPropagation();
          }}
          onWheel={(e) => {
            e.stopPropagation();
          }}
          onPointerDownCapture={(e) => {
            e.stopPropagation();
          }}
          onPointerDown={(e) => {
            e.stopPropagation();
          }}
          onMouseDownCapture={(e) => {
            e.stopPropagation();
          }}
          onMouseDown={(e) => {
            e.stopPropagation();
          }}
          className="nowheel nodrag nopan absolute left-0 right-0 top-full mt-1 z-50 rounded-lg border border-border bg-popover/95 backdrop-blur-md shadow-xl overscroll-contain overflow-y-auto max-h-72 animate-in fade-in-50 zoom-in-95 duration-100"
        >
          {errorMsg && (
            <div className="p-2 text-[11px] text-amber-500 bg-amber-500/10 border-b border-border flex items-center gap-1.5">
              <AlertCircle size={12} />
              <span>{errorMsg}</span>
            </div>
          )}

          {results.length > 0 ? (
            <div>
              <div className="px-2.5 py-1 text-[10px] text-muted-foreground font-semibold bg-muted/40 border-b border-border/40 flex justify-between items-center">
                <span>
                  {getCurrentSearchToken(inputValue)
                    ? t('security.search_results', { defaultValue: '匹配股票标的' })
                    : t('security.recent_or_popular', { defaultValue: '常用与推荐标的' })}
                </span>
                {totalMatches > results.length && (
                  <span className="text-zinc-500 font-normal">
                    {t('security.more_matches', { count: totalMatches - results.length, defaultValue: `还有 ${totalMatches - results.length} 个结果，请继续输入` })}
                  </span>
                )}
              </div>

              <ul className="divide-y divide-border/20" role="listbox">
                {results.map((sec, idx) => {
                  const isSelected = activeIndex === idx;
                  return (
                    <li
                      key={sec.symbol}
                      ref={(el) => {
                        itemRefs.current[idx] = el;
                      }}
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => commitSelection(sec)}
                      onMouseEnter={() => setActiveIndex(idx)}
                      className={`px-3 py-2 cursor-pointer text-xs flex items-center justify-between transition-colors ${
                        isSelected ? 'bg-accent text-accent-foreground font-medium' : 'hover:bg-muted/50 text-foreground'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 w-14">
                          {sec.symbol}
                        </span>
                        <span className="truncate max-w-[130px] font-medium text-foreground">
                          {sec.name}
                        </span>
                        {getExchangeBadge(sec.exchange, sec.board)}
                      </div>

                      <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                        <span className="hidden sm:inline text-zinc-500">{sec.exchange_name}</span>
                        {isSelected && <Check size={12} className="text-emerald-500" />}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : !isLoading && getCurrentSearchToken(inputValue) ? (
            <div className="p-4 text-center text-xs text-muted-foreground space-y-1">
              <div className="font-medium text-foreground">
                {t('security.no_match', { defaultValue: '未找到匹配股票' })}
              </div>
              <div className="text-[11px] text-muted-foreground">
                {t('security.no_match_tip', { defaultValue: '请检查代码、名称或拼音缩写；您仍可直接按回车或输入纯数字代码执行。' })}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
};

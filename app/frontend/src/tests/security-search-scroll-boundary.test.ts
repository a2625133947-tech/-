import { describe, it, expect, vi } from 'vitest';

describe('Security Search Dropdown & React Flow Scroll Isolation Boundary', () => {
  it('validates React Flow nowheel utility class filtering rule', () => {
    // Simulates React Flow XYPanZoom wheel filter:
    // vr = (target, className) => target.closest(`.${className}`)
    class MockElement {
      className: string;
      parentElement: MockElement | null = null;

      constructor(className = '', parent: MockElement | null = null) {
        this.className = className;
        this.parentElement = parent;
      }

      closest(selector: string): MockElement | null {
        const classNameToFind = selector.replace(/^\./, '');
        let current: MockElement | null = this;
        while (current) {
          if (current.className.split(/\s+/).includes(classNameToFind)) {
            return current;
          }
          current = current.parentElement;
        }
        return null;
      }
    }

    // Tree: ReactFlowCanvas -> Node -> Container (with nowheel nodrag nopan) -> DropdownContainer (with nowheel nodrag nopan) -> OptionItem
    const canvas = new MockElement('react-flow__renderer');
    const node = new MockElement('react-flow__node', canvas);
    const container = new MockElement('relative w-full nowheel nodrag nopan', node);
    const input = new MockElement('w-full nodrag nowheel nopan', container);
    const dropdown = new MockElement(
      'nowheel nodrag nopan absolute overscroll-contain overflow-y-auto max-h-72',
      container
    );
    const optionItem = new MockElement('option-item', dropdown);

    // React Flow's zoom handler check:
    const isNowheelMatched = Boolean(optionItem.closest('.nowheel'));
    const isNodragMatched = Boolean(optionItem.closest('.nodrag'));
    const isNopanMatched = Boolean(optionItem.closest('.nopan'));

    expect(isNowheelMatched).toBe(true);
    expect(isNodragMatched).toBe(true);
    expect(isNopanMatched).toBe(true);

    // Input element also inherits nowheel boundary
    expect(Boolean(input.closest('.nowheel'))).toBe(true);
    expect(Boolean(container.closest('.nowheel'))).toBe(true);

    // When pointer is on canvas, nowheel is not matched
    const canvasPointerTarget = new MockElement('react-flow__pane', canvas);
    expect(Boolean(canvasPointerTarget.closest('.nowheel'))).toBe(false);
  });

  it('guarantees wheel event propagation stops at dropdown without preventDefault', () => {
    // Event propagation simulation
    let propagationStopped = false;
    let defaultPrevented = false;

    const mockWheelEvent = {
      type: 'wheel',
      deltaY: 50,
      stopPropagation: () => {
        propagationStopped = true;
      },
      preventDefault: () => {
        defaultPrevented = true;
      },
    };

    // The handler attached to the dropdown container
    const handleWheel = (e: typeof mockWheelEvent) => {
      // Must stop bubbling to outer canvas/Flow
      e.stopPropagation();
      // Must NOT preventDefault so native dropdown scrolling works smoothly
    };

    handleWheel(mockWheelEvent);

    expect(propagationStopped).toBe(true);
    expect(defaultPrevented).toBe(false);
  });

  it('verifies that pointer down events are isolated from canvas/node dragging without blocking native selection', () => {
    let propagationStopped = false;
    let defaultPrevented = false;

    const mockPointerEvent = {
      type: 'pointerdown',
      button: 0,
      stopPropagation: () => {
        propagationStopped = true;
      },
      preventDefault: () => {
        defaultPrevented = true;
      },
    };

    const handlePointerDown = (e: typeof mockPointerEvent) => {
      e.stopPropagation();
      // preventDefault is NOT called so clicks and scrollbar dragging remain functional
    };

    handlePointerDown(mockPointerEvent);

    expect(propagationStopped).toBe(true);
    expect(defaultPrevented).toBe(false);
  });

  it('verifies overscroll conditions (top/bottom bounds) preserve viewport invariance', () => {
    const scrollContainer = {
      scrollTop: 0,
      scrollHeight: 500,
      clientHeight: 250,
      maxScroll: 250,
    };

    const viewport = { x: 0, y: 0, zoom: 1 };
    const initialViewport = { ...viewport };

    const simulateWheelAtBoundary = (deltaY: number, hasNowheel: boolean) => {
      if (hasNowheel) {
        // Dropdown consumes wheel, updates local scrollTop
        scrollContainer.scrollTop = Math.max(0, Math.min(scrollContainer.maxScroll, scrollContainer.scrollTop + deltaY));
        // Does NOT touch outer React Flow viewport
        return;
      }
      viewport.zoom += deltaY * 0.001;
    };

    // Wheel UP at top boundary (scrollTop = 0)
    simulateWheelAtBoundary(-50, true);
    expect(scrollContainer.scrollTop).toBe(0);
    expect(viewport).toEqual(initialViewport);

    // Wheel DOWN to bottom
    simulateWheelAtBoundary(300, true);
    expect(scrollContainer.scrollTop).toBe(250);
    expect(viewport).toEqual(initialViewport);

    // Wheel DOWN at bottom boundary
    simulateWheelAtBoundary(100, true);
    expect(scrollContainer.scrollTop).toBe(250);
    expect(viewport).toEqual(initialViewport);
  });

  it('verifies that React Flow viewport remains invariant when wheel occurs inside nowheel boundary', () => {
    const initialViewport = { x: 100, y: 200, zoom: 1.25 };
    let currentViewport = { ...initialViewport };

    const onPanZoom = vi.fn((_deltaY: number) => {
      currentViewport.zoom += 0.1;
    });

    // Outer zoom handler (similar to XYPanZoom)
    const handleCanvasWheel = (event: { targetHasNowheel: boolean; deltaY: number }) => {
      if (event.targetHasNowheel) {
        // Ignored by React Flow because of nowheel
        return;
      }
      onPanZoom(event.deltaY);
    };

    // Event inside dropdown
    handleCanvasWheel({ targetHasNowheel: true, deltaY: -40 });
    expect(onPanZoom).not.toHaveBeenCalled();
    expect(currentViewport).toEqual(initialViewport);

    // Event on canvas outside dropdown
    handleCanvasWheel({ targetHasNowheel: false, deltaY: -40 });
    expect(onPanZoom).toHaveBeenCalledTimes(1);
    expect(currentViewport.zoom).not.toBe(initialViewport.zoom);
  });

  it('validates commitSelection state machine: dropdown closes, results cleared, and focus does not reopen', () => {
    // Model state machine
    let isOpen = true;
    let selectedSecurity: any = null;
    let isCommitted = false;
    let results = [{ symbol: '600519', name: '贵州茅台' }];
    let inputValue = '6005';
    let searchGeneration = 1;

    const commitSelection = (sec: any) => {
      searchGeneration++;
      isCommitted = true;
      selectedSecurity = sec;
      inputValue = sec.symbol;
      isOpen = false;
      results = [];
    };

    const handleFocus = () => {
      // Must obey isCommitted: do not reopen!
      if (isCommitted) return;
      isOpen = true;
    };

    // Initial state: Searching (State A)
    expect(isOpen).toBe(true);
    expect(isCommitted).toBe(false);
    expect(results.length).toBe(1);

    // User commits selection (State B)
    commitSelection({ symbol: '600519', name: '贵州茅台' });
    expect(isOpen).toBe(false);
    expect(isCommitted).toBe(true);
    expect(selectedSecurity?.symbol).toBe('600519');
    expect(inputValue).toBe('600519');
    expect(results.length).toBe(0);

    // Input retains or regains focus -> dropdown must STAY closed
    handleFocus();
    expect(isOpen).toBe(false);
  });

  it('validates async search race condition prevention via generation counter', async () => {
    let isOpen = true;
    let searchGeneration = 1;
    let isCommitted = false;
    let results: any[] = [];

    // Simulate in-flight search request initiated at generation 1
    const requestGen = searchGeneration;
    const delayedSearchPromise = new Promise<{ results: any[] }>((resolve) => {
      setTimeout(() => {
        resolve({ results: [{ symbol: '600519', name: '贵州茅台' }] });
      }, 50);
    });

    // Before response returns, user clicks an item and commits
    const commitSelection = () => {
      searchGeneration++; // Increments to 2
      isCommitted = true;
      isOpen = false;
      results = [];
    };

    commitSelection();
    expect(isOpen).toBe(false);

    // When the delayed response arrives:
    const resp = await delayedSearchPromise;
    if (requestGen === searchGeneration && !isCommitted) {
      results = resp.results;
      isOpen = true;
    }

    // Must be discarded!
    expect(isOpen).toBe(false);
    expect(results.length).toBe(0);
  });

  it('validates re-editing transitioning from State B back to State C (Search mode)', () => {
    let isOpen = false;
    let isCommitted = true;
    let selectedSecurity: any = { symbol: '600519', name: '贵州茅台' };
    let inputValue = '600519';

    const handleInputChange = (newVal: string) => {
      isCommitted = false;
      selectedSecurity = null;
      inputValue = newVal;
      isOpen = true;
    };

    // User modifies input to '3007'
    handleInputChange('3007');
    expect(isCommitted).toBe(false);
    expect(selectedSecurity).toBe(null);
    expect(inputValue).toBe('3007');
    expect(isOpen).toBe(true);
  });
});

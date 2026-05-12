/**
 * Virtualized list wrapper for history sidebars.
 *
 * 用 `@tanstack/react-virtual` 虚拟化历史行渲染（仅当 items.length 超过阈值时启用）。
 *
 * 设计要点：
 *   1. 阈值以下 (< VIRTUALIZE_THRESHOLD) 直接 inline 渲染，保持与原非虚拟实现 1:1 行为。
 *   2. 阈值以上启用 useVirtualizer + measureElement (变高行支持)。
 *   3. Hover/Action menu portals 通过 children 末尾的 trailing 节点继续渲染（始终在 DOM 中，
 *      不受 visibleItems 切片影响 — portal 本来就 createPortal 到 document.body）。
 *   4. 自动滚动至选中项通过暴露 scrollToIndex API（外层 useEffect 监听 selectedId 变化时调用）。
 *
 * 注意：row 组件保持完全不变 — 这层只是包一层 transform 定位 + measureRef。
 */

import React, { useCallback, useImperativeHandle, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';

/**
 * 阈值以下不启用虚拟化 —— 与原始非虚拟实现等价行为。
 * 50 项以下，每行 ~70-100px → 总高 < 5000px，浏览器原生滚动绰绰有余，
 * 反而虚拟化会引入 measureElement 抖动风险。
 */
export const VIRTUALIZE_THRESHOLD = 50;

export interface VirtualizedHistoryListHandle {
  /**
   * 滚动指定 index 到可见区域（与原 itemEl.scrollIntoView({ block: 'nearest' }) 等价语义）。
   * 当未启用虚拟化时返回 false（由调用方继续走 DOM ref scrollIntoView 兜底）。
   */
  scrollToIndex: (index: number) => boolean;
  /** 当前是否启用了虚拟化（< 阈值时为 false）。 */
  isVirtualized: boolean;
}

export interface VirtualizedHistoryListProps<T> {
  items: T[];
  /** 给 useVirtualizer 的初始估算行高（变高行，最终用 measureElement 修正）。 */
  estimatedRowHeight?: number;
  /** overscan 行数（默认 4）。 */
  overscan?: number;
  /** 渲染单行 — 必须将 `measureRef` 挂到行最外层 DOM 上以启用变高测量。 */
  renderRow: (item: T, index: number, measureRef: (el: HTMLElement | null) => void) => React.ReactNode;
  /** key extractor（默认假设 item 有 id）。 */
  getKey?: (item: T, index: number) => string | number;
  /** 列表外层 className（默认 overflow-y-auto 起来自己当 scroll container）。 */
  className?: string;
  /**
   * 外部 scroll element 来源 — 若 ImageExpandView/VideoHistorySidebar 由 GenViewLayout 提供
   * 滚动容器，则传该容器的 getter，免得嵌套出双 scrollbar。
   *
   * 返回 `null` 时虚拟化禁用（视作 isVirtualized=false 走非虚拟分支）。
   */
  getScrollElement?: () => HTMLElement | null;
  /** trailing 节点（hover preview / action menu portal、loading 占位、空态等）。 */
  children?: React.ReactNode;
}

interface DefaultIdItem {
  id?: string | number;
}

function defaultGetKey<T>(item: T, index: number): string | number {
  const id = (item as DefaultIdItem)?.id;
  return id ?? index;
}

function VirtualizedHistoryListInner<T>(
  {
    items,
    estimatedRowHeight = 88,
    overscan = 4,
    renderRow,
    getKey = defaultGetKey,
    className,
    getScrollElement,
    children,
  }: VirtualizedHistoryListProps<T>,
  ref: React.ForwardedRef<VirtualizedHistoryListHandle>
) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = items.length >= VIRTUALIZE_THRESHOLD;

  // 不启用虚拟化时仍把 ref 暴露出来以便调用方 scrollToIndex 走 ref-based 兜底
  useImperativeHandle(
    ref,
    () => ({
      scrollToIndex: (index: number) => {
        if (!shouldVirtualize) return false;
        // virtualizer 实例在 hook 内部声明 —— 通过闭包引用
        virtualizerRef.current?.scrollToIndex(index, { align: 'auto' });
        return true;
      },
      isVirtualized: shouldVirtualize,
    }),
    [shouldVirtualize]
  );

  const estimateSize = useCallback(() => estimatedRowHeight, [estimatedRowHeight]);
  const measureRowHeight = useCallback(
    (el: Element) => el?.getBoundingClientRect().height ?? estimatedRowHeight,
    [estimatedRowHeight]
  );

  const virtualizer = useVirtualizer({
    count: shouldVirtualize ? items.length : 0,
    getScrollElement: () => (getScrollElement ? getScrollElement() : scrollRef.current),
    estimateSize,
    overscan,
    measureElement: measureRowHeight,
  });

  // 用 ref 镜像 virtualizer instance 给 useImperativeHandle 使用（避免依赖循环）
  const virtualizerRef = useRef(virtualizer);
  virtualizerRef.current = virtualizer;

  // noop measureRef — 非虚拟分支不需要测量
  const noopMeasure = useCallback(() => {}, []);

  const virtualItems = shouldVirtualize ? virtualizer.getVirtualItems() : [];
  const totalSize = shouldVirtualize ? virtualizer.getTotalSize() : 0;

  // 非虚拟分支：直接 map 出全部 row（保持与原实现 1:1 行为）
  if (!shouldVirtualize) {
    return (
      <div ref={scrollRef} className={className}>
        {items.map((item, index) => (
          <React.Fragment key={getKey(item, index)}>
            {renderRow(item, index, noopMeasure)}
          </React.Fragment>
        ))}
        {children}
      </div>
    );
  }

  // 虚拟分支
  // 注意：absolute 定位的 row 之间没有 margin/space-y 生效，必须靠 row 内部 paddingBottom
  // 留 gap（10px ≈ tailwind space-y-2.5）。measureElement 会把 padding 计入测高。
  return (
    <div ref={scrollRef} className={className}>
      <div
        style={{ height: totalSize, width: '100%', position: 'relative' }}
        data-virtualized-history-list
      >
        {virtualItems.map((virtualRow) => {
          const item = items[virtualRow.index];
          if (!item) return null;
          return (
            <div
              key={getKey(item, virtualRow.index)}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualRow.start}px)`,
                paddingBottom: 10,
              }}
            >
              {renderRow(item, virtualRow.index, () => {})}
            </div>
          );
        })}
      </div>
      {children}
    </div>
  );
}

export const VirtualizedHistoryList = React.forwardRef(VirtualizedHistoryListInner) as <T>(
  props: VirtualizedHistoryListProps<T> & { ref?: React.ForwardedRef<VirtualizedHistoryListHandle> }
) => ReturnType<typeof VirtualizedHistoryListInner>;

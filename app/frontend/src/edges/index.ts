import type { EdgeTypes } from '@xyflow/react';
import { DeletableEdge } from './deletable-edge';

export const edgeTypes = {
  default: DeletableEdge,
  deletable: DeletableEdge,
} satisfies EdgeTypes;

export { DeletableEdge };

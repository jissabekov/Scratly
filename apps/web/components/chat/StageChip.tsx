'use client';

import { stageLabel } from '../../lib/session';

type Props = {
  stage: string;
};

export function StageChip({ stage }: Props) {
  if (!stage) return null;
  return (
    <span className="stage-chip" data-stage={stage} key={stage}>
      {stageLabel(stage)}
    </span>
  );
}

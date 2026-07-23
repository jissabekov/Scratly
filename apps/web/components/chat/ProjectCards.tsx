'use client';

import type { StudentProject } from '../../lib/types';

type Props = {
  projects: StudentProject[];
};

export function ProjectCards({ projects }: Props) {
  if (!projects.length) return null;
  return (
    <div className="project-cards enter">
      {projects.map((project) => (
        <article key={project.id} className="project-card">
          <h3>{project.title}</h3>
          <p>{project.summary}</p>
          <div className="project-meta">
            {project.topic_keys.slice(0, 3).map((k) => (
              <span key={k}>{k.replaceAll('_', ' ')}</span>
            ))}
            {project.citation_count > 0 ? (
              <span>{project.citation_count} source{project.citation_count === 1 ? '' : 's'}</span>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}

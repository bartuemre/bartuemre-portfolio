import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const projectSchema = z.object({
    title: z.string(),
    summary: z.string(),
    category: z.string(),
    status: z.string(),
    stage: z.enum(['in-progress', 'demo', 'local']),
    tags: z.array(z.string()),
    featured: z.boolean().default(false),
    order: z.number(),
    repository: z.url().optional(),
    demo: z.url().optional(),
    visual: z.enum(['soc', 'research', 'iprv']),
  });
const projects = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/projects' }),
  schema: projectSchema,
});
const projectsTr = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/projects-tr' }),
  schema: projectSchema,
});

export const collections = { projects, projectsTr };

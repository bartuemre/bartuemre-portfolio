import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const projects = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/projects' }),
  schema: z.object({
    title: z.string(),
    summary: z.string(),
    category: z.enum(['Security & optimization', 'Software & research']),
    status: z.string(),
    tags: z.array(z.string()),
    featured: z.boolean().default(false),
    order: z.number(),
    repository: z.url().optional(),
    demo: z.url().optional(),
    visual: z.enum(['soc', 'research', 'iprv']),
  }),
});

export const collections = { projects };

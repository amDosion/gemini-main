/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/

export interface Candidate {
  name: string; 
}

export interface Attribute {
  name:string;
  presence_in_prompt: boolean;
  value: Candidate[];
}

export interface Entity {
  name: string;
  presence_in_prompt: boolean;
  description: string;
  alternatives: Candidate[] | null;
  attributes: Attribute[];
}

export interface Relationship {
  source: string;
  target: string;
  label: string;
  alternatives?: Candidate[];
}

export interface BeliefState {
  entities: Entity[];
  relationships: Relationship[];
  prompt?: string;
}

export interface Clarification {
  question: string;
  options: string[];
}

export type GraphUpdate = 
  | { type: 'attribute'; entity: string; attribute: string; value: string }
  | { type: 'relationship'; source: string; target: string; oldLabel: string; newLabel: string };

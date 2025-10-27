import axios from 'axios';

const KG_API_BASE_URL = process.env.NEXT_PUBLIC_KG_API_URL || 'http://localhost:8006';

export interface Entity {
  id: string;
  labels: string[];
  properties: {
    text: string;
    label: string;
    confidence?: number;
    source?: string;
  };
}

export interface Relationship {
  type: string;
  properties: {
    confidence?: number;
  };
  target: {
    id: string;
    labels: string[];
    properties: {
      text: string;
      label?: string;
    };
  };
}

export interface EntityWithRelations {
  id: string;
  labels: string[];
  properties: any;
  relations: Relationship[];
}

export interface Path {
  nodes: Array<{
    text: string;
    labels: string[];
  }>;
  relations: string[];
}

export interface GraphStatistics {
  total_nodes: number;
  total_relationships: number;
  label_statistics: Array<{
    label: string;
    count: number;
  }>;
}

export interface ExtractResponse {
  success: boolean;
  entities_extracted: number;
  entities_stored: number;
  relations_extracted: number;
  relations_stored: number;
  error?: string;
}

class KnowledgeGraphAPI {
  private baseURL: string;

  constructor(baseURL: string = KG_API_BASE_URL) {
    this.baseURL = baseURL;
  }

  async extractFromText(text: string, source?: string): Promise<ExtractResponse> {
    const response = await axios.post(`${this.baseURL}/api/v1/kg/extract`, {
      text,
      source,
    });
    return response.data;
  }

  async queryEntity(entity: string): Promise<EntityWithRelations> {
    const response = await axios.post(`${this.baseURL}/api/v1/kg/query/entity`, {
      entity,
    });
    return response.data;
  }

  async queryPath(
    startEntity: string,
    endEntity: string,
    maxDepth: number = 3
  ): Promise<{ paths: Path[]; count: number }> {
    const response = await axios.post(`${this.baseURL}/api/v1/kg/query/path`, {
      start_entity: startEntity,
      end_entity: endEntity,
      max_depth: maxDepth,
    });
    return response.data;
  }

  async getNeighbors(
    entity: string,
    maxNeighbors: number = 10
  ): Promise<{ neighbors: Entity[]; count: number }> {
    const response = await axios.post(`${this.baseURL}/api/v1/kg/query/neighbors`, {
      entity,
      max_neighbors: maxNeighbors,
    });
    return response.data;
  }

  async getStatistics(): Promise<GraphStatistics> {
    const response = await axios.get(`${this.baseURL}/api/v1/kg/statistics`);
    return response.data;
  }

  async healthCheck(): Promise<any> {
    const response = await axios.get(`${this.baseURL}/api/v1/kg/health`);
    return response.data;
  }
}

export const kgApi = new KnowledgeGraphAPI();


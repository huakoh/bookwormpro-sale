#!/usr/bin/env python3
"""
Database Schema Generator
Converts analyzed requirements into database schema files
"""

import json
import sys
import argparse
from typing import Dict, List, Any

class SchemaGenerator:
    def __init__(self, framework: str = "prisma"):
        self.framework = framework
        
    def generate_from_entities(self, entities: List[Dict[str, Any]]) -> str:
        """Generate schema from entity definitions"""
        if self.framework == "prisma":
            return self._generate_prisma(entities)
        elif self.framework == "sqlalchemy":
            return self._generate_sqlalchemy(entities)
        elif self.framework == "typeorm":
            return self._generate_typeorm(entities)
        elif self.framework == "sql":
            return self._generate_sql(entities)
        else:
            raise ValueError(f"Unsupported framework: {self.framework}")
    
    def _generate_prisma(self, entities: List[Dict[str, Any]]) -> str:
        """Generate Prisma schema"""
        schema = """datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

"""
        for entity in entities:
            schema += f"model {entity['name']} {{\n"
            
            # Add fields
            for field in entity['fields']:
                field_type = self._map_type_prisma(field['type'])
                modifiers = []
                
                if field.get('primary'):
                    modifiers.append("@id @default(uuid())")
                if field.get('unique'):
                    modifiers.append("@unique")
                if field.get('required', True):
                    field_type += ""
                else:
                    field_type += "?"
                if field.get('default'):
                    modifiers.append(f"@default({field['default']})")
                
                modifier_str = " ".join(modifiers)
                schema += f"  {field['name']} {field_type} {modifier_str}\n"
            
            # Add relationships
            for rel in entity.get('relationships', []):
                rel_type = f"{rel['target']}[]" if rel['type'] == 'many' else rel['target']
                if rel['type'] == 'one':
                    rel_type += "?"
                schema += f"  {rel['name']} {rel_type}\n"
            
            # Add timestamps
            schema += "  createdAt DateTime @default(now())\n"
            schema += "  updatedAt DateTime @updatedAt\n"
            
            schema += "}\n\n"
        
        return schema
    
    def _generate_sqlalchemy(self, entities: List[Dict[str, Any]]) -> str:
        """Generate SQLAlchemy models"""
        code = """from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

"""
        for entity in entities:
            code += f"class {entity['name']}(Base):\n"
            code += f"    __tablename__ = '{entity['name'].lower()}s'\n\n"
            
            # Add fields
            for field in entity['fields']:
                col_type = self._map_type_sqlalchemy(field['type'])
                constraints = []
                
                if field.get('primary'):
                    constraints.append("primary_key=True")
                    constraints.append("default=uuid.uuid4")
                if field.get('unique'):
                    constraints.append("unique=True")
                if field.get('required', True):
                    constraints.append("nullable=False")
                
                constraint_str = ", ".join(constraints)
                code += f"    {field['name']} = Column({col_type}, {constraint_str})\n"
            
            # Add timestamps
            code += "    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)\n"
            code += "    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)\n"
            
            # Add relationships
            for rel in entity.get('relationships', []):
                code += f"    {rel['name']} = relationship('{rel['target']}')\n"
            
            code += "\n"
        
        return code
    
    def _generate_typeorm(self, entities: List[Dict[str, Any]]) -> str:
        """Generate TypeORM entities"""
        code = """import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn, ManyToOne, OneToMany } from 'typeorm';

"""
        for entity in entities:
            code += "@Entity()\n"
            code += f"export class {entity['name']} {{\n"
            
            # Add fields
            for field in entity['fields']:
                decorators = []
                
                if field.get('primary'):
                    decorators.append("  @PrimaryGeneratedColumn('uuid')")
                else:
                    col_type = self._map_type_typescript(field['type'])
                    options = []
                    if field.get('unique'):
                        options.append("unique: true")
                    if not field.get('required', True):
                        options.append("nullable: true")
                    
                    option_str = f", {{ {', '.join(options)} }}" if options else ""
                    decorators.append(f"  @Column('{col_type}'{option_str})")
                
                ts_type = self._map_type_typescript(field['type'])
                nullable = "" if field.get('required', True) else " | null"
                
                code += "\n".join(decorators) + "\n"
                code += f"  {field['name']}: {ts_type}{nullable};\n\n"
            
            # Add timestamps
            code += "  @CreateDateColumn()\n"
            code += "  createdAt: Date;\n\n"
            code += "  @UpdateDateColumn()\n"
            code += "  updatedAt: Date;\n"
            
            code += "}\n\n"
        
        return code
    
    def _generate_sql(self, entities: List[Dict[str, Any]]) -> str:
        """Generate SQL DDL"""
        sql = "-- Database Schema\n\n"
        
        for entity in entities:
            table_name = entity['name'].lower() + 's'
            sql += f"CREATE TABLE {table_name} (\n"
            
            fields = []
            
            # Add fields
            for field in entity['fields']:
                col_type = self._map_type_sql(field['type'])
                constraints = []
                
                if field.get('primary'):
                    constraints.append("PRIMARY KEY")
                    constraints.append("DEFAULT gen_random_uuid()")
                if field.get('unique'):
                    constraints.append("UNIQUE")
                if field.get('required', True):
                    constraints.append("NOT NULL")
                
                constraint_str = " ".join(constraints)
                fields.append(f"    {field['name']} {col_type} {constraint_str}")
            
            # Add timestamps
            fields.append("    created_at TIMESTAMP DEFAULT NOW() NOT NULL")
            fields.append("    updated_at TIMESTAMP DEFAULT NOW() NOT NULL")
            
            sql += ",\n".join(fields)
            sql += "\n);\n\n"
            
            # Add indexes for foreign keys
            for rel in entity.get('relationships', []):
                if rel.get('foreign_key'):
                    sql += f"CREATE INDEX idx_{table_name}_{rel['name']} ON {table_name}({rel['name']}_id);\n"
            
            sql += "\n"
        
        return sql
    
    def _map_type_prisma(self, field_type: str) -> str:
        """Map generic type to Prisma type"""
        mapping = {
            'string': 'String',
            'text': 'String',
            'integer': 'Int',
            'float': 'Float',
            'boolean': 'Boolean',
            'date': 'DateTime',
            'datetime': 'DateTime',
            'uuid': 'String',
            'json': 'Json'
        }
        return mapping.get(field_type.lower(), 'String')
    
    def _map_type_sqlalchemy(self, field_type: str) -> str:
        """Map generic type to SQLAlchemy type"""
        mapping = {
            'string': 'String(255)',
            'text': 'Text',
            'integer': 'Integer',
            'float': 'Float',
            'boolean': 'Boolean',
            'date': 'DateTime',
            'datetime': 'DateTime',
            'uuid': 'UUID(as_uuid=True)',
            'json': 'JSON'
        }
        return mapping.get(field_type.lower(), 'String(255)')
    
    def _map_type_typescript(self, field_type: str) -> str:
        """Map generic type to TypeScript type"""
        mapping = {
            'string': 'string',
            'text': 'string',
            'integer': 'number',
            'float': 'number',
            'boolean': 'boolean',
            'date': 'Date',
            'datetime': 'Date',
            'uuid': 'string',
            'json': 'object'
        }
        return mapping.get(field_type.lower(), 'string')
    
    def _map_type_sql(self, field_type: str) -> str:
        """Map generic type to SQL type"""
        mapping = {
            'string': 'VARCHAR(255)',
            'text': 'TEXT',
            'integer': 'INTEGER',
            'float': 'DECIMAL(10,2)',
            'boolean': 'BOOLEAN',
            'date': 'DATE',
            'datetime': 'TIMESTAMP',
            'uuid': 'UUID',
            'json': 'JSONB'
        }
        return mapping.get(field_type.lower(), 'VARCHAR(255)')


def main():
    parser = argparse.ArgumentParser(description='Generate database schema from entity definitions')
    parser.add_argument('--input', required=True, help='JSON file with entity definitions')
    parser.add_argument('--framework', default='prisma', 
                       choices=['prisma', 'sqlalchemy', 'typeorm', 'sql'],
                       help='Target framework/format')
    parser.add_argument('--output', help='Output file (default: stdout)')
    
    args = parser.parse_args()
    
    # Load entities
    with open(args.input, 'r') as f:
        data = json.load(f)
    
    entities = data if isinstance(data, list) else data.get('entities', [])
    
    # Generate schema
    generator = SchemaGenerator(args.framework)
    schema = generator.generate_from_entities(entities)
    
    # Output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(schema)
        print(f"✅ Schema generated: {args.output}")
    else:
        print(schema)


if __name__ == '__main__':
    main()

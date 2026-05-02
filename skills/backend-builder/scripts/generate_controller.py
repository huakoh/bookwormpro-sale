#!/usr/bin/env python3
"""
Controller/Route Generator
Creates CRUD controllers and route definitions from models
"""

import argparse
import os
from pathlib import Path

class ControllerGenerator:
    def __init__(self, framework: str):
        self.framework = framework
        
    def generate(self, model_name: str, output_dir: str = "."):
        """Generate controller and routes for a model"""
        if self.framework == "express":
            return self._generate_express(model_name, output_dir)
        elif self.framework == "fastapi":
            return self._generate_fastapi(model_name, output_dir)
        elif self.framework == "nestjs":
            return self._generate_nestjs(model_name, output_dir)
        else:
            raise ValueError(f"Unsupported framework: {self.framework}")
    
    def _generate_express(self, model_name: str, output_dir: str):
        """Generate Express.js controller and routes"""
        model_lower = model_name.lower()
        model_plural = model_lower + 's'
        
        # Controller file
        controller_code = f'''const {{ {model_name} }} = require('../models/{model_lower}');
const {{ validationResult }} = require('express-validator');

// @desc    Get all {model_plural}
// @route   GET /api/{model_plural}
// @access  Public
exports.getAll{model_name}s = async (req, res) => {{
    try {{
        const {{ page = 1, limit = 20, sort = '-createdAt' }} = req.query;
        const skip = (page - 1) * limit;
        
        const {model_plural} = await {model_name}.find()
            .sort(sort)
            .skip(skip)
            .limit(parseInt(limit));
        
        const total = await {model_name}.countDocuments();
        
        res.json({{
            success: true,
            data: {model_plural},
            pagination: {{
                page: parseInt(page),
                limit: parseInt(limit),
                total,
                totalPages: Math.ceil(total / limit)
            }}
        }});
    }} catch (error) {{
        res.status(500).json({{
            success: false,
            error: {{ message: 'Server error', details: error.message }}
        }});
    }}
}};

// @desc    Get single {model_lower}
// @route   GET /api/{model_plural}/:id
// @access  Public
exports.get{model_name} = async (req, res) => {{
    try {{
        const {model_lower} = await {model_name}.findById(req.params.id);
        
        if (!{model_lower}) {{
            return res.status(404).json({{
                success: false,
                error: {{ message: '{model_name} not found' }}
            }});
        }}
        
        res.json({{
            success: true,
            data: {model_lower}
        }});
    }} catch (error) {{
        res.status(500).json({{
            success: false,
            error: {{ message: 'Server error', details: error.message }}
        }});
    }}
}};

// @desc    Create {model_lower}
// @route   POST /api/{model_plural}
// @access  Private
exports.create{model_name} = async (req, res) => {{
    try {{
        const errors = validationResult(req);
        if (!errors.isEmpty()) {{
            return res.status(400).json({{
                success: false,
                error: {{
                    message: 'Validation failed',
                    details: errors.array()
                }}
            }});
        }}
        
        const {model_lower} = await {model_name}.create(req.body);
        
        res.status(201).json({{
            success: true,
            data: {model_lower},
            message: '{model_name} created successfully'
        }});
    }} catch (error) {{
        res.status(500).json({{
            success: false,
            error: {{ message: 'Server error', details: error.message }}
        }});
    }}
}};

// @desc    Update {model_lower}
// @route   PUT /api/{model_plural}/:id
// @access  Private
exports.update{model_name} = async (req, res) => {{
    try {{
        const {model_lower} = await {model_name}.findByIdAndUpdate(
            req.params.id,
            req.body,
            {{ new: true, runValidators: true }}
        );
        
        if (!{model_lower}) {{
            return res.status(404).json({{
                success: false,
                error: {{ message: '{model_name} not found' }}
            }});
        }}
        
        res.json({{
            success: true,
            data: {model_lower},
            message: '{model_name} updated successfully'
        }});
    }} catch (error) {{
        res.status(500).json({{
            success: false,
            error: {{ message: 'Server error', details: error.message }}
        }});
    }}
}};

// @desc    Delete {model_lower}
// @route   DELETE /api/{model_plural}/:id
// @access  Private
exports.delete{model_name} = async (req, res) => {{
    try {{
        const {model_lower} = await {model_name}.findByIdAndDelete(req.params.id);
        
        if (!{model_lower}) {{
            return res.status(404).json({{
                success: false,
                error: {{ message: '{model_name} not found' }}
            }});
        }}
        
        res.json({{
            success: true,
            message: '{model_name} deleted successfully'
        }});
    }} catch (error) {{
        res.status(500).json({{
            success: false,
            error: {{ message: 'Server error', details: error.message }}
        }});
    }}
}};
'''
        
        # Routes file
        routes_code = f'''const express = require('express');
const router = express.Router();
const {{ body }} = require('express-validator');
const {{
    getAll{model_name}s,
    get{model_name},
    create{model_name},
    update{model_name},
    delete{model_name}
}} = require('../controllers/{model_lower}Controller');
const {{ protect }} = require('../middleware/auth');

// Validation rules
const create{model_name}Validation = [
    body('name').notEmpty().withMessage('Name is required'),
    // Add more validation rules as needed
];

// Public routes
router.get('/', getAll{model_name}s);
router.get('/:id', get{model_name});

// Protected routes
router.post('/', protect, create{model_name}Validation, create{model_name});
router.put('/:id', protect, update{model_name});
router.delete('/:id', protect, delete{model_name});

module.exports = router;
'''
        
        # Write files
        controller_path = Path(output_dir) / "controllers" / f"{model_lower}Controller.js"
        routes_path = Path(output_dir) / "routes" / f"{model_lower}Routes.js"
        
        controller_path.parent.mkdir(parents=True, exist_ok=True)
        routes_path.parent.mkdir(parents=True, exist_ok=True)
        
        controller_path.write_text(controller_code)
        routes_path.write_text(routes_code)
        
        return {
            'controller': str(controller_path),
            'routes': str(routes_path)
        }
    
    def _generate_fastapi(self, model_name: str, output_dir: str):
        """Generate FastAPI router"""
        model_lower = model_name.lower()
        model_plural = model_lower + 's'
        
        router_code = f'''from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..models.{model_lower} import {model_name}
from ..schemas.{model_lower} import {model_name}Create, {model_name}Update, {model_name}Response
from ..auth import get_current_user

router = APIRouter(prefix="/{model_plural}", tags=["{model_plural}"])

@router.get("/", response_model=dict)
async def get_{model_plural}(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get all {model_plural} with pagination"""
    skip = (page - 1) * limit
    
    {model_plural} = db.query({model_name}).offset(skip).limit(limit).all()
    total = db.query({model_name}).count()
    
    return {{
        "success": True,
        "data": {model_plural},
        "pagination": {{
            "page": page,
            "limit": limit,
            "total": total,
            "totalPages": (total + limit - 1) // limit
        }}
    }}

@router.get("/{{id}}", response_model={model_name}Response)
async def get_{model_lower}(id: str, db: Session = Depends(get_db)):
    """Get single {model_lower} by ID"""
    {model_lower} = db.query({model_name}).filter({model_name}.id == id).first()
    
    if not {model_lower}:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    
    return {model_lower}

@router.post("/", response_model={model_name}Response, status_code=201)
async def create_{model_lower}(
    {model_lower}_data: {model_name}Create,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new {model_lower}"""
    {model_lower} = {model_name}(**{model_lower}_data.dict())
    db.add({model_lower})
    db.commit()
    db.refresh({model_lower})
    
    return {model_lower}

@router.put("/{{id}}", response_model={model_name}Response)
async def update_{model_lower}(
    id: str,
    {model_lower}_data: {model_name}Update,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update {model_lower}"""
    {model_lower} = db.query({model_name}).filter({model_name}.id == id).first()
    
    if not {model_lower}:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    
    for key, value in {model_lower}_data.dict(exclude_unset=True).items():
        setattr({model_lower}, key, value)
    
    db.commit()
    db.refresh({model_lower})
    
    return {model_lower}

@router.delete("/{{id}}", status_code=200)
async def delete_{model_lower}(
    id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete {model_lower}"""
    {model_lower} = db.query({model_name}).filter({model_name}.id == id).first()
    
    if not {model_lower}:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    
    db.delete({model_lower})
    db.commit()
    
    return {{"success": True, "message": "{model_name} deleted successfully"}}
'''
        
        router_path = Path(output_dir) / "routers" / f"{model_lower}.py"
        router_path.parent.mkdir(parents=True, exist_ok=True)
        router_path.write_text(router_code)
        
        return {'router': str(router_path)}
    
    def _generate_nestjs(self, model_name: str, output_dir: str):
        """Generate NestJS controller"""
        model_lower = model_name.lower()
        model_plural = model_lower + 's'
        
        controller_code = f'''import {{
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Body,
  Param,
  Query,
  UseGuards,
  HttpCode,
  HttpStatus,
}} from '@nestjs/common';
import {{ {model_name}Service }} from './{model_lower}.service';
import {{ Create{model_name}Dto, Update{model_name}Dto }} from './dto';
import {{ JwtAuthGuard }} from '../auth/guards/jwt-auth.guard';

@Controller('{model_plural}')
export class {model_name}Controller {{
  constructor(private readonly {model_lower}Service: {model_name}Service) {{}}

  @Get()
  async findAll(
    @Query('page') page: number = 1,
    @Query('limit') limit: number = 20,
  ) {{
    return this.{model_lower}Service.findAll(page, limit);
  }}

  @Get(':id')
  async findOne(@Param('id') id: string) {{
    return this.{model_lower}Service.findOne(id);
  }}

  @Post()
  @UseGuards(JwtAuthGuard)
  @HttpCode(HttpStatus.CREATED)
  async create(@Body() create{model_name}Dto: Create{model_name}Dto) {{
    return this.{model_lower}Service.create(create{model_name}Dto);
  }}

  @Put(':id')
  @UseGuards(JwtAuthGuard)
  async update(
    @Param('id') id: string,
    @Body() update{model_name}Dto: Update{model_name}Dto,
  ) {{
    return this.{model_lower}Service.update(id, update{model_name}Dto);
  }}

  @Delete(':id')
  @UseGuards(JwtAuthGuard)
  async remove(@Param('id') id: string) {{
    return this.{model_lower}Service.remove(id);
  }}
}}
'''
        
        controller_path = Path(output_dir) / model_lower / f"{model_lower}.controller.ts"
        controller_path.parent.mkdir(parents=True, exist_ok=True)
        controller_path.write_text(controller_code)
        
        return {'controller': str(controller_path)}


def main():
    parser = argparse.ArgumentParser(description='Generate CRUD controller and routes')
    parser.add_argument('--model', required=True, help='Model name (e.g., User)')
    parser.add_argument('--framework', required=True, 
                       choices=['express', 'fastapi', 'nestjs'],
                       help='Backend framework')
    parser.add_argument('--output', default='.', help='Output directory')
    
    args = parser.parse_args()
    
    generator = ControllerGenerator(args.framework)
    files = generator.generate(args.model, args.output)
    
    print(f"✅ Generated controller files:")
    for file_type, path in files.items():
        print(f"   {file_type}: {path}")


if __name__ == '__main__':
    main()

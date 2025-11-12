from typing import Optional, List
from supabase import create_client, Client
from app.config import settings
from app.models.tenant import Tenant, TenantConfig
import logging

logger = logging.getLogger(__name__)

class TenantService:
    def __init__(self):
        self.supabase: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
    
    async def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug"""
        try:
            response = self.supabase.table('tenants').select("*").eq('slug', slug).single().execute()
            if response.data:
                tenant_data = response.data
                tenant_data['config'] = TenantConfig(**tenant_data['config'])
                return Tenant(**tenant_data)
            return None
        except Exception as e:
            logger.error(f"Error fetching tenant by slug {slug}: {e}")
            return None
    
    async def get_tenant_by_id(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        try:
            response = self.supabase.table('tenants').select("*").eq('id', tenant_id).single().execute()
            if response.data:
                tenant_data = response.data
                tenant_data['config'] = TenantConfig(**tenant_data['config'])
                return Tenant(**tenant_data)
            return None
        except Exception as e:
            logger.error(f"Error fetching tenant by id {tenant_id}: {e}")
            return None
    
    async def list_tenants(self) -> List[Tenant]:
        """List all active tenants"""
        try:
            response = self.supabase.table('tenants').select("*").execute()
            tenants = []
            for tenant_data in response.data:
                tenant_data['config'] = TenantConfig(**tenant_data['config'])
                tenants.append(Tenant(**tenant_data))
            return tenants
        except Exception as e:
            logger.error(f"Error listing tenants: {e}")
            return []
    
    async def validate_tenant_boundaries(self, tenant: Tenant, lat: float, lng: float) -> bool:
        """Check if coordinates are within tenant boundaries"""
        boundaries = tenant.config.boundaries
        return (
            boundaries.south <= lat <= boundaries.north and
            boundaries.west <= lng <= boundaries.east
        )
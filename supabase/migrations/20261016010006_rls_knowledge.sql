-- PLAN 1.3.d: who may read components, installations and knowledge (decision 0023).
-- Staff see everything at their supplier, drafts included. Plant users see the components
-- and installations at their plants, and only approved knowledge (CLAUDE.md invariant 2:
-- drafts are never shown or used live). Rules and ingestion issues are staff-only.


create policy "staff see all components; plant users those at their plants"
  on public.components for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or plant_id in (select unnest(private.my_plants())))
  );

create policy "staff see all installations; plant users those at their plants"
  on public.installations for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and (
      (select private.is_staff())
      or exists (
        select 1 from public.components c
         where c.id = installations.component_id
           and c.plant_id in (select unnest(private.my_plants()))
      )
    )
  );

create policy "staff see every playbook version; plant users approved ones"
  on public.playbooks for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or status = 'approved')
  );

create policy "staff see all vocabulary; plant users approved terms"
  on public.vocab_terms for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or status = 'approved')
  );

create policy "staff see all products; plant users approved ones"
  on public.products for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and ((select private.is_staff()) or status = 'approved')
  );

create policy "staff see all product images; plant users those of approved products"
  on public.product_images for select to authenticated
  using (
    tenant_id = (select private.my_tenant())
    and (
      (select private.is_staff())
      or exists (
        select 1 from public.products p
         where p.id = product_images.product_id and p.status = 'approved'
      )
    )
  );

create policy "staff see the rules" on public.rules
  for select to authenticated
  using (tenant_id = (select private.my_tenant()) and (select private.is_staff()));

create policy "staff see ingestion issues" on public.ingestion_issues
  for select to authenticated
  using (tenant_id = (select private.my_tenant()) and (select private.is_staff()));

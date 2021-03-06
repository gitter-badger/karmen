insert into public.users (uuid, username, email, system_role, providers, providers_data, activated)
  values ('1b59f2e0-336f-4a1c-8caf-1f074fc43744', 'karmen', 'karmen@karmen.local', 'admin', '{"local"}', '{}', now())
  on conflict do nothing;

update public.users set system_role = 'admin'
  where uuid = '1b59f2e0-336f-4a1c-8caf-1f074fc43744';

-- password is karmen3D
insert into public.local_users (user_uuid, pwd_hash, force_pwd_change)
  values ('1b59f2e0-336f-4a1c-8caf-1f074fc43744', '$2y$12$6w9ml13UTA2Re2GcqDHFJuVHB3WLlPPyg430vrve/hrjR5yWO0LYm', true)
  on conflict do nothing;

insert into public.organization_roles (organization_uuid, user_uuid, role)
  values ('b3060e41-e319-4a9b-8ac4-e0936c75f275', '1b59f2e0-336f-4a1c-8caf-1f074fc43744', 'admin')
  on conflict do nothing;
----
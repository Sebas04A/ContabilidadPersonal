import { useMemo, useState } from 'react';
import {
  useRules,
  useCategories,
  useSaveEntityRule,
  useDeleteEntityRule,
  useRenameEntityRule,
  useSaveTagRule,
  useDeleteTagRule,
  useSaveMapRule,
  useDeleteMapRule,
} from '../../hooks/useTransactions';
import { EntityRule, TagRule } from '../../services/api';
import {
  ArrowRight,
  Flame,
  Heart,
  Loader2,
  Pencil,
  Plus,
  Search,
  Store,
  Tag as TagIcon,
  Trash2,
  Wand2,
  X,
} from 'lucide-react';

type Section = 'entity' | 'tag' | 'map';

const SECTIONS: { id: Section; label: string; icon: JSX.Element; hint: string }[] = [
  {
    id: 'entity',
    label: 'Entidades',
    icon: <Store size={16} />,
    hint: 'Nombre limpio → categoría, prioridad, tags, nota',
  },
  {
    id: 'tag',
    label: 'Tags',
    icon: <TagIcon size={16} />,
    hint: 'Tag → categoría y prioridad por defecto',
  },
  {
    id: 'map',
    label: 'Descripciones',
    icon: <Wand2 size={16} />,
    hint: 'Texto del banco → nombre limpio',
  },
];

// Editing state for the modal: null = closed.
type Draft =
  | { section: 'entity'; key: string; original: string | null; rule: EntityRule }
  | { section: 'tag'; key: string; original: string | null; rule: TagRule }
  | { section: 'map'; key: string; original: string | null; clean: string };

export function RulesManager() {
  const [section, setSection] = useState<Section>('entity');
  const [search, setSearch] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const { data: rules, isLoading } = useRules();
  const { data: categories } = useCategories();

  const saveEntity = useSaveEntityRule();
  const deleteEntity = useDeleteEntityRule();
  const renameEntity = useRenameEntityRule();
  const saveTag = useSaveTagRule();
  const deleteTag = useDeleteTagRule();
  const saveMap = useSaveMapRule();
  const deleteMap = useDeleteMapRule();

  const isSaving =
    saveEntity.isPending || saveTag.isPending || saveMap.isPending || renameEntity.isPending;

  // Filtered rows for the active section.
  const rows = useMemo(() => {
    if (!rules) return [] as [string, any][];
    const source =
      section === 'entity' ? rules.entity_data : section === 'tag' ? rules.tag_data : rules.description_map;
    const q = search.trim().toLowerCase();
    return Object.entries(source)
      .filter(([key, val]) => !q || key.toLowerCase().includes(q) || JSON.stringify(val).toLowerCase().includes(q))
      .sort(([a], [b]) => a.localeCompare(b));
  }, [rules, section, search]);

  const openNew = () => {
    if (section === 'entity') setDraft({ section: 'entity', key: '', original: null, rule: {} });
    else if (section === 'tag') setDraft({ section: 'tag', key: '', original: null, rule: {} });
    else setDraft({ section: 'map', key: '', original: null, clean: '' });
  };

  const handleSave = async () => {
    if (!draft || !draft.key.trim()) return;
    const key = draft.key.trim();

    if (draft.section === 'entity') {
      // A renamed entity keeps its description mappings pointing at it.
      if (draft.original && draft.original !== key) {
        await renameEntity.mutateAsync({ oldName: draft.original, newName: key });
      }
      await saveEntity.mutateAsync({ name: key, rule: draft.rule });
    } else if (draft.section === 'tag') {
      if (draft.original && draft.original !== key) {
        await deleteTag.mutateAsync(draft.original);
      }
      await saveTag.mutateAsync({ tag: key, rule: draft.rule });
    } else {
      if (draft.original && draft.original !== key) {
        await deleteMap.mutateAsync(draft.original);
      }
      await saveMap.mutateAsync({ original: key, clean: draft.clean });
    }
    setDraft(null);
  };

  const handleDelete = (key: string) => {
    if (section === 'entity') deleteEntity.mutate(key);
    else if (section === 'tag') deleteTag.mutate(key);
    else deleteMap.mutate(key);
    setConfirmDelete(null);
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-8 pb-8 custom-scrollbar">
      <div className="max-w-[1400px] mx-auto space-y-6 mt-4">
        {/* Section switcher */}
        <div className="glass-card p-5 flex flex-wrap items-center justify-between gap-4 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-96 h-96 bg-purple-500/5 rounded-full blur-[100px] pointer-events-none"></div>

          <div className="flex items-center gap-2 relative z-10 flex-wrap">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => setSection(s.id)}
                className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all border ${
                  section === s.id
                    ? 'bg-purple-500/20 text-purple-100 border-purple-500/40 shadow-lg shadow-purple-500/10'
                    : 'bg-white/5 text-gray-400 border-white/5 hover:bg-white/10 hover:text-white'
                }`}
              >
                {s.icon}
                {s.label}
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/30">
                  {rules
                    ? s.id === 'entity'
                      ? rules.counts.entity_data
                      : s.id === 'tag'
                      ? rules.counts.tag_data
                      : rules.counts.description_map
                    : '–'}
                </span>
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3 relative z-10">
            <div className="flex items-center gap-2 bg-white/5 border border-white/10 rounded-xl px-3 py-2">
              <Search size={15} className="text-gray-500" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar regla…"
                className="bg-transparent text-sm text-white outline-none w-44"
              />
              {search && (
                <button onClick={() => setSearch('')} className="text-gray-500 hover:text-white">
                  <X size={14} />
                </button>
              )}
            </div>
            <button
              onClick={openNew}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-pink-500 text-white font-bold text-sm hover:shadow-[0_0_25px_rgba(168,85,247,0.35)] transition-all active:scale-95"
            >
              <Plus size={16} /> Nueva regla
            </button>
          </div>
        </div>

        <p className="text-xs text-gray-500 px-2">{SECTIONS.find((s) => s.id === section)?.hint}</p>

        {/* Rules list */}
        <div className="glass-card overflow-hidden">
          {isLoading ? (
            <div className="py-24 flex justify-center">
              <Loader2 className="animate-spin text-purple-400" size={28} />
            </div>
          ) : (
            <div className="overflow-auto max-h-[70vh] custom-scrollbar">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-900/95 backdrop-blur-sm z-10">
                  <tr className="text-[10px] uppercase tracking-widest text-gray-500">
                    <th className="text-left px-5 py-3 font-bold">
                      {section === 'map' ? 'Texto del banco' : section === 'tag' ? 'Tag' : 'Nombre limpio'}
                    </th>
                    <th className="text-left px-3 py-3 font-bold">
                      {section === 'map' ? 'Nombre limpio' : 'Categoría'}
                    </th>
                    {section !== 'map' && (
                      <>
                        <th className="text-left px-3 py-3 font-bold">Prioridad</th>
                        <th className="text-left px-3 py-3 font-bold">Fijo</th>
                        {section === 'entity' && <th className="text-left px-3 py-3 font-bold">Tags</th>}
                        <th className="text-left px-3 py-3 font-bold">Nota</th>
                      </>
                    )}
                    <th className="w-24 px-5 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(([key, val]) => (
                    <tr key={key} className="border-t border-white/5 hover:bg-white/[0.03] group">
                      <td className="px-5 py-3 max-w-[340px]">
                        <div className="truncate text-white font-medium">{key}</div>
                      </td>

                      {section === 'map' ? (
                        <td className="px-3 py-3 text-gray-300">
                          <span className="flex items-center gap-2">
                            <ArrowRight size={13} className="text-gray-600" />
                            {String(val)}
                          </span>
                        </td>
                      ) : (
                        <>
                          <td className="px-3 py-3 text-gray-400">{val.categoria || '—'}</td>
                          <td className="px-3 py-3">
                            {val.prioridad && val.prioridad !== '---' ? (
                              <span
                                className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                                  val.prioridad === 'Necesidad'
                                    ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                                    : 'bg-pink-500/10 text-pink-300 border-pink-500/20'
                                }`}
                              >
                                {val.prioridad}
                              </span>
                            ) : (
                              <span className="text-gray-600">—</span>
                            )}
                          </td>
                          <td className="px-3 py-3 text-gray-400 text-xs">{val.es_fijo ? 'Sí' : '—'}</td>
                          {section === 'entity' && (
                            <td className="px-3 py-3 text-gray-500 text-xs max-w-[200px] truncate">
                              {val.tags || '—'}
                            </td>
                          )}
                          <td className="px-3 py-3 text-gray-600 text-xs max-w-[180px] truncate">
                            {val.nota || '—'}
                          </td>
                        </>
                      )}

                      <td className="px-5 py-3">
                        <div className="flex items-center gap-1 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() =>
                              setDraft(
                                section === 'map'
                                  ? { section: 'map', key, original: key, clean: String(val) }
                                  : section === 'tag'
                                  ? { section: 'tag', key, original: key, rule: { ...val } }
                                  : { section: 'entity', key, original: key, rule: { ...val } }
                              )
                            }
                            className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-colors"
                            title="Editar"
                          >
                            <Pencil size={15} />
                          </button>
                          <button
                            onClick={() => setConfirmDelete(key)}
                            className="p-2 rounded-lg hover:bg-red-500/20 text-gray-400 hover:text-red-300 transition-colors"
                            title="Eliminar"
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!rows.length && (
                    <tr>
                      <td colSpan={7} className="text-center py-16 text-gray-600">
                        {search ? 'Ninguna regla coincide' : 'Todavía no hay reglas aquí'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Delete confirmation */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="glass-card p-6 max-w-md w-full space-y-4">
            <h3 className="text-lg font-bold text-white">¿Eliminar esta regla?</h3>
            <p className="text-sm text-gray-400 break-words">
              <span className="text-white font-medium">{confirmDelete}</span>
              <br />
              Las transacciones ya etiquetadas no cambian; solo dejará de aplicarse a las nuevas.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setConfirmDelete(null)}
                className="px-4 py-2 rounded-xl bg-white/5 text-gray-300 hover:bg-white/10 text-sm font-bold"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleDelete(confirmDelete)}
                className="px-4 py-2 rounded-xl bg-red-500/20 text-red-300 hover:bg-red-500 hover:text-white text-sm font-bold transition-colors"
              >
                Eliminar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Editor modal */}
      {draft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="glass-card p-6 max-w-lg w-full space-y-5 max-h-[90vh] overflow-y-auto custom-scrollbar">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">
                {draft.original ? 'Editar regla' : 'Nueva regla'} ·{' '}
                {SECTIONS.find((s) => s.id === draft.section)?.label}
              </h3>
              <button onClick={() => setDraft(null)} className="p-2 rounded-lg hover:bg-white/10 text-gray-400">
                <X size={18} />
              </button>
            </div>

            <label className="flex flex-col gap-1.5">
              <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">
                {draft.section === 'map'
                  ? 'Texto que aparece en el banco'
                  : draft.section === 'tag'
                  ? 'Tag'
                  : 'Nombre limpio'}
              </span>
              <input
                value={draft.key}
                onChange={(e) => setDraft({ ...draft, key: e.target.value })}
                placeholder={draft.section === 'map' ? 'UBER   *TRIP' : 'Supermaxi'}
                className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50"
              />
              {draft.section === 'map' && (
                <span className="text-[11px] text-gray-600">
                  Se busca como subcadena, sin distinguir mayúsculas.
                </span>
              )}
            </label>

            {draft.section === 'map' ? (
              <label className="flex flex-col gap-1.5">
                <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">
                  Nombre limpio resultante
                </span>
                <input
                  value={draft.clean}
                  onChange={(e) => setDraft({ ...draft, clean: e.target.value })}
                  list="rule-entities"
                  placeholder="Uber"
                  className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50"
                />
                <datalist id="rule-entities">
                  {Object.keys(rules?.entity_data || {}).map((n) => (
                    <option key={n} value={n} />
                  ))}
                </datalist>
              </label>
            ) : (
              <>
                <label className="flex flex-col gap-1.5">
                  <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Categoría</span>
                  <input
                    value={draft.rule.categoria || ''}
                    onChange={(e) => setDraft({ ...draft, rule: { ...draft.rule, categoria: e.target.value } })}
                    list="rule-categories"
                    className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50"
                  />
                  <datalist id="rule-categories">
                    {(categories || []).map((c) => (
                      <option key={c} value={c} />
                    ))}
                  </datalist>
                </label>

                <div className="flex flex-col gap-1.5">
                  <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Prioridad</span>
                  <div className="flex gap-2">
                    {(['Necesidad', 'Deseo', ''] as const).map((p) => (
                      <button
                        key={p || 'none'}
                        onClick={() => setDraft({ ...draft, rule: { ...draft.rule, prioridad: p } })}
                        className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-xl border text-xs font-bold uppercase tracking-wider transition-all ${
                          (draft.rule.prioridad || '') === p
                            ? 'bg-purple-500/20 text-purple-100 border-purple-500/40'
                            : 'bg-white/5 text-gray-500 border-white/10 hover:text-white'
                        }`}
                      >
                        {p === 'Necesidad' && <Flame size={13} />}
                        {p === 'Deseo' && <Heart size={13} />}
                        {p || 'Sin definir'}
                      </button>
                    ))}
                  </div>
                </div>

                {draft.section === 'entity' && (
                  <label className="flex flex-col gap-1.5">
                    <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Tags</span>
                    <input
                      value={draft.rule.tags || ''}
                      onChange={(e) => setDraft({ ...draft, rule: { ...draft.rule, tags: e.target.value } })}
                      placeholder="tag1, tag2"
                      className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50"
                    />
                  </label>
                )}

                <label className="flex flex-col gap-1.5">
                  <span className="text-[10px] uppercase font-bold tracking-widest text-gray-500">Nota</span>
                  <input
                    value={draft.rule.nota || ''}
                    onChange={(e) => setDraft({ ...draft, rule: { ...draft.rule, nota: e.target.value } })}
                    className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50"
                  />
                </label>

                <label className="flex items-center gap-2.5 text-sm text-gray-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!draft.rule.es_fijo}
                    onChange={(e) => setDraft({ ...draft, rule: { ...draft.rule, es_fijo: e.target.checked } })}
                    className="accent-purple-500 w-4 h-4"
                  />
                  Es un gasto fijo
                </label>
              </>
            )}

            <div className="flex gap-3 justify-end pt-2">
              <button
                onClick={() => setDraft(null)}
                className="px-4 py-2 rounded-xl bg-white/5 text-gray-300 hover:bg-white/10 text-sm font-bold"
              >
                Cancelar
              </button>
              <button
                onClick={handleSave}
                disabled={!draft.key.trim() || isSaving}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-pink-500 text-white text-sm font-bold disabled:opacity-40 flex items-center gap-2 transition-all active:scale-95"
              >
                {isSaving && <Loader2 size={14} className="animate-spin" />}
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

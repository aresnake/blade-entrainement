# BLADE — Fab Acceptance Baseline V0

Date : 2026-08-31
Statut : BASELINE SOURCEE — à distinguer des budgets internes BLADE

## 1. Principe

BLADE ne doit pas inventer de chiffres de triangles, texel density ou LOD en les présentant
comme des exigences Fab. Les exigences officielles actuellement publiées doivent être
séparées des budgets internes choisis pour la qualité et la performance.

Source principale : Epic Developer Community, « Asset File Format and Structure Requirements
in Fab ».

## 2. Exigences Fab directement exploitables

Les exigences générales publiées incluent notamment :

- absence de défauts visuels ;
- produit complet ;
- fonctionnement conforme à la description ;
- fichiers additionnels pertinents au produit.

Pour les modèles 3D, Fab ne publie pas dans cette page un budget universel fixe de
triangles applicable à tous les props. La règle publiée est d'optimiser la géométrie en
utilisant le nombre de polygones le plus faible possible tout en conservant silhouette et
détails.

## 3. Géométrie

La documentation Fab recommande :

- uniquement triangles ou quadrilatères, pas de ngons ;
- normales correctes et lissées lorsque nécessaire ;
- pivot/origine correctement placé ;
- transformations propres avant export ;
- absence de géométrie non-manifold ;
- vérification des performances pour les usages mobile / AR / VR / web lorsque concernés.

Ces points sont de bons candidats pour des contrôles BLADE automatisables.

## 4. Textures / matériaux

La documentation Fab recommande :

- workflow PBR ;
- textures en puissances de deux ;
- éviter les textures > 4K sauf nécessité ;
- matériaux correctement configurés ;
- un matériau par surface ou objet selon le contexte documenté.

La documentation de Fab Launcher fournit également des suffixes reconnus pour le
mapping automatique (`basecolor`, `normal`, `roughness`, `metallic`, etc.).

## 5. Nommage

La documentation Fab Launcher recommande pour les noms de fichiers :

- minuscules ;
- underscores plutôt que espaces ;
- éviter les caractères non ASCII.

BLADE peut adopter une convention plus stricte en interne, mais celle-ci doit être déclarée
comme convention BLADE et non comme exigence universelle Fab.

## 6. LOD et triangle budgets

À ce stade, aucune source officielle consultée n'établit un budget universel Fab du type
« X triangles maximum par asset » ni une densité de texel universelle obligatoire pour tous
les produits.

Décision BLADE :

- ne pas inventer ces valeurs ;
- définir plus tard des budgets internes par famille / niveau de détail / cible ;
- documenter séparément la justification technique de chaque budget ;
- faire échouer le QC BLADE sur les budgets internes seulement lorsqu'ils sont explicitement
  adoptés comme critères de production.

## 7. Conséquence architecture QC

Le pipeline de validation doit distinguer au minimum :

```text
FAB_REQUIRED
    exigences issues des sources officielles

BLADE_QUALITY
    règles internes de qualité géométrique / texture / structure

TARGET_BUDGET
    budgets de production choisis pour une cible donnée
```

Un rapport QC ne doit jamais mélanger ces trois catégories.

## 8. Source

Epic Developer Community — Fab Documentation :
« Asset File Format and Structure Requirements in Fab ».

Autre source officielle consultée :
« Setting up Assets for Fab in Launcher ».

Les liens exacts et la date de consultation doivent être conservés dans la documentation
finale du projet avant publication.

"""Live create -> read -> update -> read -> delete -> read round trips for the
/db/* resources a real modelling script actually touches, against a real
Gen NX / Civil NX session.

The read-only counterpart, scripts/live_readonly_sweep.py, proves an endpoint
exists and answers. This proves the SDK's *write* shapes are the ones the
server actually accepts: that ``create()``'s "Assign" body lands, that a
``get()`` echoes back what was written, that ``update()`` changes it, and that
``delete()`` removes it. A TypedDict transcribed with a wrong field name will
pass every mocked test in tests/ and only fail here.

Cases are grouped into **tiers**, run in priority order — the order in which a
modelling script needs them, not the order the manual lists them:

    core       the proven baseline (groups, nodes, elements, load cases, loads)
    props      material / section sub-types (thickness, stiffness factors,
               time-dependent material)
    boundary   springs and links
    static     the rest of ch06's static loads, plus ch07 element/nodal
               temperature
    stage      construction stages and what attaches to them
    moving     moving-load chain (code -> lane -> vehicle -> case). Its
               fixtures are AASHTO LRFD/HL-93 (rebuilt 2026-07-30 from
               Korea-standard, cross-checked against a real production
               arch-bridge model's own data) and kept Civil-only here for
               now, pending an actual Gen run; the underlying routes answer
               on Gen too but per-CODE, not unconditionally (see the tier's
               own comment) — /db/CMCS in the stage tier is the one still
               genuinely Civil-only

``--tier`` runs a subset. Every tier declares its own seed, so a tier is
runnable on its own.

Fixture design
--------------
Most first-run failures in this checker have been bad fixtures, not SDK bugs
(4 of 4 on the first Civil run, 2026-07-26). Two rules keep it that way:

1. **Seed first, then take the next id.** Definition tables disagree about
   whether they honour the ``"Assign"`` key: /db/NODE does (posting under 77
   yields node 77), /db/STLD does not (it renumbers to the next free slot).
   So a seeded record goes in at the lowest free key and its case takes the
   *next sequential* key — under either behaviour both land on the same id.
   Where a record can be referenced by name (structure/boundary/load groups,
   spring types, lanes, vehicles) the fixtures reference it by name and the
   id question never arises.
2. **Nothing a case deletes may be another case's prerequisite.** Seeded
   records are suffixed ``_SEED`` and no case touches them.

Failure classification
----------------------
A checker that cries wolf gets ignored, so the report separates:

    regression   a case that has completed this round trip live before broke
                 -> treat as an SDK defect until proven otherwise
    unverified   a case that has never passed live failed -> triage the
                 fixture payload first; it is not yet evidence about the SDK
    blocked      a seed step this case declared a need for failed, so the
                 case never ran -> fixture
    skipped      quarantined: calling the endpoint is known to hang or kill
                 MIDAS NX, so it is not run unless --include-crashers

``Case.confirmed=True`` marks the cases that have actually passed against a
live server. Flip a case to ``confirmed=True`` only after you have watched it
pass, and say where in the comment. As of 2026-07-29, all 43 are confirmed
on Civil NX 2026 v2.2 (and 40 of them on v2.1 as well).

/db/NMAS was quarantined from 2026-07-26 until 2026-07-29: a POST omitting
its optional rmX/rmY/rmZ fields reliably killed both Civil NX and Gen NX
(15+ reproductions). The root cause turned out to be exactly that omission
- sending the fields explicitly (even as 0.0) doesn't crash it - so
NodalMass.create()/.update() now fill them in and this case runs
unquarantined. --include-crashers still exists for any future case that
needs it.

DESTRUCTIVE. It calls /doc/NEW and builds a throwaway model. Never point it at
a session holding work you care about.

⚠️ /doc/NEW on a document with unsaved changes raises MIDAS's own save-changes
dialog, and that dialog blocks the entire API session until a human clicks it -
the next call fails for reasons unrelated to itself. Have a human present, or
start from a saved document.

⚠️ The checkpoint exists to clear that dialog by saving first, but /doc/SAVEAS
is not safe to automate blind: given a path NX dislikes it raises a modal
"invalid path" error dialog, blocks the session until someone clicks it, and
then returns {"message": "... command complete"} anyway - the same string a
real save returns, with no file on disk. Verified 2026-07-26 on Civil NX.
Check the file exists yourself afterwards; do not trust the response.

--save-dir names a directory ON THE NX MACHINE and the checkpoint name is
derived from the product, so the NX extension cannot be got wrong; --save-as
takes an exact path instead, extension included; --no-save-before waives the
checkpoint but not the /doc/NEW. One of the three is required, the same rule
all four destructive harnesses follow - see scripts/harness_save_path.py.

Run with the dev environment active (``pip install -e ".[dev]"``), e.g.:
    python scripts/live_crud_check.py --product civil --save-dir C:/temp
    python scripts/live_crud_check.py --product civil --save-dir C:/temp         --tier core,boundary
    python scripts/live_crud_check.py --product civil --save-as C:/tmp/scratch.mcbz
    python scripts/live_crud_check.py --product civil --save-dir C:/temp --out crud.json

Exit code 0 -> every case that ran completed a full round trip.
Exit code 1 -> a previously-confirmed case regressed (SDK defect suspect).
Exit code 2 -> couldn't connect, or the server rejected the connection.
Exit code 3 -> only unverified failures / blocked cases (triage the fixtures).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from midas_nx import doc
from midas_nx.client import MidasAPIError, MidasClient
from midas_nx.db.analysis_control import (
    AssignBoundaryCombinationHyperS,
    BoundaryChangeAssignment,
    BucklingAnalysisControl,
    ConstructionStageAnalysisControlData,
    ConstructionStageAnalysisControlDataHyperS,
    DefineBoundaryCombinationHyperS,
    EigenvalueAnalysisControl,
    EigenvalueAnalysisControlHyperS,
    HeatOfHydrationAnalysisControl,
    HeatOfHydrationAnalysisControlHyperS,
    MainControlData,
    MainControlDataHyperS,
    MovingLoadAnalysisControl,
    MovingLoadAnalysisControlBS,
    MovingLoadAnalysisControlIndia,
    MovingLoadAnalysisControlTransverse,
    NonlinearAnalysisControlData,
    NonlinearAnalysisControlHyperS,
    PDeltaAnalysisControl,
    SettlementAnalysisControlData,
)
from midas_nx.db.boundary import (
    BeamEndOffset,
    BeamEndRelease,
    ChangeGeneralLinkProperty,
    Constraint,
    ConstraintLabelDirection,
    ElasticLink,
    ForceDeformationFunction,
    GeneralLink,
    GeneralLinkHyperS,
    GeneralLinkProperty,
    GeneralSpringSupport,
    GeneralSpringType,
    LinearConstraint,
    PanelZoneEffect,
    PlateEndRelease,
    PointSpring,
    RigidLink,
    SeismicDeviceHystereticIsolator,
    SeismicDeviceIsolator,
    SeismicDeviceSteelDamper,
    SeismicDeviceViscoelasticDamper,
    SeismicDeviceViscousDamper,
    SurfaceSpring,
)
from midas_nx.db.bridge import (
    BridgeGirderDiagram,
    FcmCamberControl,
    GeneralCamberControl,
    UnknownLoadFactorConstraint,
)
from midas_nx.db.construction_stage import (
    AmbientTemperatureFunction,
    AssignHeatSource,
    CamberConstructionStage,
    ConstructionStage,
    ConstructionStageForHydration,
    ConvectionCoefficientFunction,
    CreepCoefficientConstructionStage,
    ElementConvectionBoundary,
    HeatSourceFunction,
    PipeCooling,
    PrescribedTemperature,
    SetBackLoad,
    TimeLoadConstructionStage,
)
from midas_nx.db.design import (
    DesignMemberAssignment,
    FrameDefinition,
    LimitingSlendernessRatio,
    ModifyMemberType,
    ModifyWallMark,
    RcDesignCode,
    SteelDesignCode,
    UnbracedLength,
)
from midas_nx.db.dynamic_loads import (
    DynamicNodalLoad,
    GroundAcceleration,
    MultipleSupportExcitation,
    ResponseSpectrumFunction,
    ResponseSpectrumLoadCase,
    TimeHistoryFunction,
    TimeHistoryGlobalControl,
    TimeHistoryGlobalControlHyperS,
    TimeHistoryLoadCase,
    TimeHistoryOutputOptionHyperS,
    TimeVaryingStaticLoad,
)
from midas_nx.db.load_combinations import (
    CuttingLine,
    LoadCombinationCompositeSteelGirder,
    LoadCombinationConcrete,
    LoadCombinationGeneral,
    LoadCombinationSeismic,
    LoadCombinationSRC,
    LoadCombinationSteel,
    PlateCuttingLineDiagram,
)
from midas_nx.db.misc_loads import (
    IgnoreElementForLoadCase,
    InitialElementForce,
    InitialForceControlData,
    InitialForceGeometricStiffness,
    LoadSequenceNonlinear,
    PreCompositeSection,
    SettlementGroup,
    SettlementLoadCase,
    WaveLoad,
)
from midas_nx.db.moving_loads import (
    AdditionalImpactFactor,
    ConcurrentJointForceGroup,
    ConcurrentReactionGroup,
    DynamicLoadAllowance,
    LaneSupportNegativeMoment,
    LaneSupportReaction,
    MovingLoadCase,
    MovingLoadCaseChina,
    MovingLoadCaseEurocode,
    MovingLoadCaseIndia,
    MovingLoadCasePoland,
    MovingLoadCaseTransverse,
    MovingLoadCode,
    PlateElementForInfluenceSurface,
    RailwayDynamicFactor,
    RailwayDynamicFactorByElement,
    TrafficLineLanes,
    TrafficLineLanesChina,
    TrafficLineLanesIndia,
    TrafficLineLanesOptimization,
    TrafficLineLanesTransverse,
    TrafficSurfaceLanes,
    TrafficSurfaceLanesChina,
    TrafficSurfaceLanesOptimization,
    VehicleClasses,
    Vehicles,
    VehiclesTransverse,
)
from midas_nx.db.node_element import (
    DomainElement,
    Element,
    MainDomain,
    Node,
    Skew,
    SubDomain,
)
from midas_nx.db.project import (
    BoundaryGroup,
    FloorLoadColor,
    LoadGroup,
    MaterialColor,
    NamedPlane,
    ProjectInfo,
    SectionColor,
    Span,
    StructureGroup,
    StructureType,
    StructureTypeHyperS,
    TendonGroup,
    ThicknessColor,
    Unit,
)
from midas_nx.db.properties.damping import GroupDamping
from midas_nx.db.properties.hinge import InelasticHingeControl
from midas_nx.db.properties.material import (
    ChangeProperty,
    InelasticMaterialProperty,
    Material,
    MaterialModifyConcrete,
    PlasticMaterial,
    TimeDependentMaterialCreepShrinkage,
    TimeDependentMaterialFunction,
    TimeDependentMaterialLink,
    TimeDependentMaterialStrength,
)
from midas_nx.db.properties.section import (
    EffectiveWidthScaleFactor,
    ElementStiffnessScaleFactor,
    PlateStiffnessScaleFactor,
    Section,
    SectionReinforcement,
    SectionStiffness,
    SectionStressPoints,
    TaperedGroup,
    VirtualBeam,
    VirtualSection,
)
from midas_nx.db.properties.thickness import Thickness
from midas_nx.db.pushover import (
    AssignPushoverHingeProperties,
    IgnoreElementsForPushoverInitialLoad,
    PushoverAnalysisControlData,
    PushoverAnalysisControlDataHyperS,
    PushoverLoadCase,
    PushoverLoadCaseHyperS,
)
from midas_nx.db.static_loads import (
    BeamLoad,
    FinishingMaterialLoad,
    FloorLoad,
    FloorLoadType,
    LoadsToMass,
    NodalBodyForce,
    NodalLoad,
    NodalMass,
    PlaneLoad,
    PlaneLoadType,
    PressureLoad,
    PressureLoadType,
    SeismicEarthPressure,
    SeismicLoadParam,
    SelfWeight,
    SoilProperty,
    SpecifiedDisplacement,
    StaticEarthPressure,
    StaticLoadCase,
)
from midas_nx.db.temperature_prestress import (
    BeamSectionTemperature,
    ElementTemperature,
    ExternalLoadCaseForPretension,
    NodalTemperature,
    PrestressBeamLoad,
    PretensionLoad,
    SystemTemperature,
    TemperatureGradient,
    TendonPrestress,
    TendonProfile,
    TendonProperty,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness_save_path  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

SIZE, HEIGHT, BAY = 0.6, 3.2, 4.0

#: How a failed case is reported. See the module docstring.
OK, REGRESSION, UNVERIFIED, BLOCKED = "ok", "regression", "unverified", "blocked"
#: Quarantined: known to hang or kill the product, so not run by default.
SKIPPED = "skipped"
LIVE_CASES_PATH = Path(__file__).resolve().parents[1] / "schema" / "live-cases.json"
LIVE_CASES_VERSION = 6

# Shared by the Python base model and the emitted npm live fixture.  Keep
# prerequisite records here rather than reproducing them in JavaScript. STLD
# assigns the next serial id instead of honoring the request key, while SKEW
# attaches to an already-existing node, so neither case can run on a truly
# blank document.
BASE_MODEL_SEEDS: Dict[str, Dict[str, Any]] = {
    # /db/DYFG and /db/DYNF need the moving-load code to be EUROCODE. Python
    # gets there by seeding KSCE-LSD15 for /db/DYLA and switching the same
    # record with extras14's own /db/MVCD case, which a per-case harness
    # cannot interleave. The record is that case's confirmed update payload.
    "mvcd_eurocode": {
        "endpoint": MovingLoadCode.ENDPOINT,
        "records": {
            "1": {"CODE": "EUROCODE"},
        },
    },
    "static_load_cases": {
        "endpoint": StaticLoadCase.ENDPOINT,
        "records": {
            "1": {"NAME": "DL", "TYPE": "D", "DESC": "Dead Load"},
            "2": {"NAME": "LC_SCRATCH", "TYPE": "L", "DESC": "crud fixture"},
        },
    },
    # The manual's LCOM-SEISMIC examples use ANAL="RS", which must reference
    # an actual Response Spectrum Load Case rather than the base model's
    # static DL. Keep the prerequisite records here for the npm harness too.
    "lcom_seismic_spfc": {
        "endpoint": ResponseSpectrumFunction.ENDPOINT,
        "records": {
            "1": {
                "NAME": "SPFC_LCOM_SEED", "iTYPE": 2, "iMETHOD": 0,
                "SCALE": 1.0, "GRAV": 9.806, "DRATIO": 0.05, "DESC": "",
                "aFUNC": [
                    {"PERIOD": 0.1, "VALUE": 0.5},
                    {"PERIOD": 0.5, "VALUE": 1.0},
                    {"PERIOD": 1.0, "VALUE": 0.3},
                ],
            },
        },
    },
    "lcom_seismic_splc": {
        "endpoint": ResponseSpectrumLoadCase.ENDPOINT,
        "records": {
            "1": {
                "NAME": "SPLC_LCOM_SEED", "DIR": "XY", "SCALE": 1.0,
                "PMFT": 1.0, "aFUNCNAME": ["SPFC_LCOM_SEED"],
            },
        },
    },
    # The LTSR record key is a real element id.  Python's base model already
    # has beam 2; npm's empty-document harness needs the same minimal chain
    # expressed as ordered, individually-cleanable setup records.
    "ltsr_material": {
        "endpoint": Material.ENDPOINT,
        # /doc/NEW supplies C24 at id 1. The npm harness may delete that
        # disposable baseline record before it creates this fixture's S450;
        # never infer this permission from an ordinary setup collision.
        "replaceExisting": True,
        "records": {
            "1": {
                "TYPE": "STEEL", "NAME": "DB_Steel", "HE_SPEC": 0,
                "HE_COND": 0, "PLMT": 0, "P_NAME": "",
                "bMASS_DENS": False, "DAMP_RAT": 0.02,
                "PARAM": [{"P_TYPE": 1, "STANDARD": "EN05(S)", "CODE": "",
                           "DB": "S450", "bELAST": False}],
            },
        },
    },
    "ltsr_section": {
        "endpoint": Section.ENDPOINT,
        # /doc/NEW supplies an unrelated concrete Column at id 1. The npm
        # fixture needs its own H beam section at that documented reference.
        "replaceExisting": True,
        "records": {
            "1": {
                "SECTTYPE": "DBUSER", "SECT_NAME": "H300x150",
                "SECT_BEFORE": {
                    "OFFSET_PT": "CC", "OFFSET_CENTER": 0,
                    "USER_OFFSET_REF": 0, "HORZ_OFFSET_OPT": 0,
                    "USERDEF_OFFSET_YI": 0, "VERT_OFFSET_OPT": 0,
                    "USERDEF_OFFSET_ZI": 0, "USE_SHEAR_DEFORM": True,
                    "USE_WARPING_EFFECT": True, "SHAPE": "H", "DATATYPE": 1,
                    "SECT_I": {"DB_NAME": "KS21", "SECT_NAME": "H300x150x6.5/9"},
                },
            },
        },
    },
    "ltsr_nodes": {
        "endpoint": Node.ENDPOINT,
        # These ids are part of the shared disposable base model. Rebuild the
        # design fixture explicitly instead of treating that known overlap as
        # an unsafe setup collision.
        "replaceExisting": True,
        "records": {
            "2": {"X": 0, "Y": 0, "Z": HEIGHT},
            "3": {"X": BAY, "Y": 0, "Z": HEIGHT},
        },
    },
    "ltsr_beam": {
        "endpoint": Element.ENDPOINT,
        "replaceExisting": True,
        "records": {
            "2": {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [2, 3]},
        },
    },
    "member_node": {
        "endpoint": Node.ENDPOINT,
        "replaceExisting": True,
        "records": {
            "4": {"X": 2 * BAY, "Y": 0, "Z": HEIGHT},
        },
    },
    "member_beam": {
        "endpoint": Element.ENDPOINT,
        "replaceExisting": True,
        "records": {
            "3": {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [3, 4]},
        },
    },
    # WMAK's WID_LIST needs an existing plate element. Keep the thickness,
    # nodes, and plate separate so the npm runner can clean each record by id.
    "wmak_thickness": {
        "endpoint": Thickness.ENDPOINT,
        # The new-document baseline also reserves id 1 for a thickness. Use
        # the fixture's named plate thickness instead of assuming equivalence.
        "replaceExisting": True,
        "records": {
            "1": {
                "NAME": "T_PLATE", "TYPE": "VALUE", "bINOUT": False,
                "T_IN": 0.2, "T_OUT": 0.0, "O_VALUE": 0.0,
            },
        },
    },
    "wmak_nodes": {
        "endpoint": Node.ENDPOINT,
        "replaceExisting": True,
        "records": {
            "1": {"X": 0, "Y": 0, "Z": 0},
            "2": {"X": BAY, "Y": 0, "Z": 0},
            "3": {"X": 0, "Y": 0, "Z": HEIGHT},
            "4": {"X": BAY, "Y": 0, "Z": HEIGHT},
        },
    },
    "wmak_plate": {
        "endpoint": Element.ENDPOINT,
        "replaceExisting": True,
        "records": {
            "4": {
                "TYPE": "PLATE", "MATL": 1, "SECT": 1,
                "NODE": [1, 2, 4, 3], "ANGLE": 0, "STYPE": 1,
            },
        },
    },
}


class Case:
    """One resource's round trip: what to write, what to change, what to check.

    ``probe`` pulls the single value the assertions compare on, so a case
    stays readable even when the payload is deeply nested. Where echoing a
    value back is itself uncertain (server-side reordering, unit conversion),
    probe something boring like NAME — the point of this checker is that the
    write lands and the delete removes it, not field-level fidelity.

    ``confirmed`` means this exact case has completed the round trip against a
    real server; only those count as regressions when they fail.
    """

    def __init__(
        self,
        resource,
        create_payload: dict,
        update_payload: dict,
        probe: Callable[[dict], Any],
        expect_created: Any,
        expect_updated: Any,
        item_id: int = 1,
        confirmed: bool = False,
        products: Optional[Sequence[str]] = None,
        needs: Sequence[str] = (),
        crashes: Optional[str] = None,
        setup: Sequence[Dict[str, Any]] = (),
        unordered: bool = False,
        setup_replaces: Sequence[str] = (),
    ) -> None:
        self.resource = resource
        self.create_payload = create_payload
        self.update_payload = update_payload
        self.probe = probe
        self.expect_created = expect_created
        self.expect_updated = expect_updated
        self.item_id = item_id
        self.confirmed = confirmed
        self.products = tuple(products) if products else ("gen", "civil")
        #: Names of the seed steps this case genuinely depends on. A case that
        #: needs nothing still runs when a sibling's seed step fails — the
        #: first live run blocked 7 cases behind one unrelated /db/TDMT seed
        #: failure, which is exactly the false-positive noise that gets a
        #: checker ignored.
        self.needs = tuple(needs)
        #: Set when calling this endpoint is known to hang or kill MIDAS NX.
        #: Such a case is skipped unless --include-crashers is passed: the
        #: cost of running it is a forced restart plus the license-recovery
        #: dance, and it takes every case after it down with it.
        self.crashes = crashes
        #: Records needed by the npm live harness before this case can run.
        #: The Python runner already has its own base-model and tier seed
        #: functions, but JavaScript must not retype those payloads.
        self.setup = tuple(setup)
        #: The server returns a list in its own order, so ``probe`` sorts it
        #: and the expected values are sorted too.  npm has no probe -- it
        #: searches the response for the expected value -- so this flag is
        #: what tells it to compare lists as multisets instead of in order.
        self.unordered = unordered
        #: Needs that this case's own ``setup`` satisfies differently for a
        #: harness that seeds each case alone, so they are neither prepended
        #: to the emitted setup nor reported blocked. Python still runs and
        #: gates on them as ``needs``.
        self.setup_replaces = tuple(setup_replaces)


class SeedStep:
    """One named, independently-failing piece of a tier's fixture."""

    def __init__(
        self,
        name: str,
        run: Callable[[MidasClient], None],
        products: Optional[Sequence[str]] = None,
    ) -> None:
        self.name = name
        self.run = run
        self.products = frozenset(products or ("gen", "civil"))


class Tier:
    """A named group of cases plus the seed steps they need.

    The seed runs immediately before the tier's cases, not once up front, so
    a tier stays runnable on its own and so a tier can rebuild something an
    earlier tier's case deleted (``moving`` re-creates /db/MVCD, which the
    ``core`` tier's own case deletes).
    """

    def __init__(self, name: str, title: str, seeds: Callable[[], List[SeedStep]],
                 cases: Callable[[], List[Case]]) -> None:
        self.name = name
        self.title = title
        self.seeds = seeds
        self.cases = cases


# --------------------------------------------------------------------------
# Base model — everything every tier can assume exists.
# --------------------------------------------------------------------------


# The base model, as data rather than as nine call sites.
#
# Python built this by calling typed resources with inline literals, so it
# existed only inside _seed_model and only Python could replay it. The npm
# harness starts from a genuinely empty /doc/NEW, which is why thirteen cases
# confirmed here could not resolve their node/element/material/section
# preconditions there and reported REGRESS for a model that was never built.
# schema/live-cases.json claims to be the language-neutral source both
# harnesses read; a base model only one of them can build is a hole in that
# claim. Emitting these steps closes it, and _seed_model now executes the same
# list it emits, so the two cannot drift.
BASE_MODEL_STEPS: List[Dict[str, Any]] = [
    {"resource": Unit, "method": "PUT",
     "records": {1: {"DIST": "M", "FORCE": "KN"}}},
    {"resource": Material, "method": "POST",
     "records": {1: {"TYPE": "CONC", "NAME": "C24",
                     "PARAM": [{"P_TYPE": 1, "STANDARD": "KS01(RC)",
                                "DB": "C24"}]}}},
    {"resource": Section, "method": "POST",
     "records": {1: {"SECTTYPE": "DBUSER", "SECT_NAME": "Column",
                     "SECT_BEFORE": {"USE_SHEAR_DEFORM": True, "SHAPE": "SB",
                                     "DATATYPE": 2,
                                     "SECT_I": {"vSIZE": [SIZE, SIZE]}}}}},
    # Thickness 1 backs the plate element; the props tier's own THIK case
    # takes id 2 so it can be deleted without taking the plate with it.
    {"resource": Thickness, "method": "POST",
     "records": {1: {"NAME": "T_SEED", "TYPE": "VALUE", "bINOUT": False,
                     "T_IN": 0.20, "T_OUT": 0, "O_VALUE": 0}}},
    {"resource": Node, "method": "POST",
     "records": {
         1: {"X": 0, "Y": 0, "Z": 0},
         2: {"X": 0, "Y": 0, "Z": HEIGHT},
         3: {"X": BAY, "Y": 0, "Z": HEIGHT},
         4: {"X": 2 * BAY, "Y": 0, "Z": HEIGHT},
         # Plate corners, offset in -Y so they can't be confused with the frame.
         5: {"X": 0, "Y": -BAY, "Z": 0},
         6: {"X": BAY, "Y": -BAY, "Z": 0},
         7: {"X": BAY, "Y": -2 * BAY, "Z": 0},
         8: {"X": 0, "Y": -2 * BAY, "Z": 0},
         # A free, unconnected pair for the link/constraint cases. Nothing
         # else attaches to these, so ELNK/RIGD/MCON can't collide with a
         # real element - but they do collide with *each other*, so those
         # three cases rely on each deleting itself before the next runs.
         21: {"X": 0, "Y": 2 * BAY, "Z": 0},
         22: {"X": 0, "Y": 2 * BAY, "Z": HEIGHT},
     }},
    {"resource": Element, "method": "POST",
     "records": {
         1: {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [1, 2]},
         2: {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [2, 3]},
         3: {"TYPE": "BEAM", "MATL": 1, "SECT": 1, "NODE": [3, 4]},
         4: {"TYPE": "PLATE", "MATL": 1, "SECT": 1, "NODE": [5, 6, 7, 8]},
     }},
    {"resource": Constraint, "method": "POST",
     "records": {1: {"ITEMS": [{"ID": 1, "CONSTRAINT": "1111111"}]}}},
    # A load case every load case below attaches to, that nothing deletes.
    {"resource": StaticLoadCase, "method": "POST",
     "records": BASE_MODEL_SEEDS["static_load_cases"]["records"]},
    {"resource": SelfWeight, "method": "POST",
     "records": {1: {"LCNAME": "DL", "FV": [0, 0, -1]}}},
]


def _seed_model(client: MidasClient) -> None:
    """Minimum model the cases attach to, replayed from BASE_MODEL_STEPS.

    Ids are chosen so that nothing here collides with a case:
      nodes    1-2 frame, 3-4 beam chain, 5-8 plate corners, 21-22 free pair
      elements 1-3 beams, 4 plate
      material 1, section 1, thickness 1, load cases 1 (DL) and 2 (LC_SCRATCH)
    """
    for step in BASE_MODEL_STEPS:
        resource = step["resource"]
        records = step["records"]
        if step["method"] == "PUT":
            resource.update(records, client=client)
        else:
            resource.create(records, client=client)


def _final_checkpoint_path(initial_path: str) -> str:
    """Return a distinct post-run checkpoint beside the user-approved path.

    Saving the pre-run document alone does not make the throwaway model clean:
    every fixture seed and CRUD case dirties the new document again.  A unique
    final path avoids a host-side overwrite prompt and lets /doc/NEW leave an
    actually empty scratch document without asking the operator to save it.
    """
    path = Path(initial_path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return str(path.with_name(f"{path.stem}-after-live-{stamp}{path.suffix}")).replace("\\", "/")


def _seed_hexahedral_solid(
    client: MidasClient, *, node_start: int, element_id: int,
    replace_existing: bool = False,
) -> None:
    """Create an isolated eight-node SOLID element for hydration fixtures.

    The official /db/ELEM manual explicitly documents ``SOLID`` as an
    eight-node hexahedral element with ``MATL``, ``SECT: 0``, and eight node
    ids.  Keep it out of the baseline model: only hydration cases need this
    geometry, and a case must never delete another case's prerequisite.
    """
    x0 = 10.0 + float(element_id)
    nodes = {
        node_start: {"X": x0, "Y": 0.0, "Z": 0.0},
        node_start + 1: {"X": x0 + 1.0, "Y": 0.0, "Z": 0.0},
        node_start + 2: {"X": x0 + 1.0, "Y": 1.0, "Z": 0.0},
        node_start + 3: {"X": x0, "Y": 1.0, "Z": 0.0},
        node_start + 4: {"X": x0, "Y": 0.0, "Z": 1.0},
        node_start + 5: {"X": x0 + 1.0, "Y": 0.0, "Z": 1.0},
        node_start + 6: {"X": x0 + 1.0, "Y": 1.0, "Z": 1.0},
        node_start + 7: {"X": x0, "Y": 1.0, "Z": 1.0},
    }
    Node.create(nodes, client=client)
    if replace_existing:
        # extras11 models a hydration-only document inside the shared
        # throwaway baseline. HECB's documented ITEMS[].ID is a serial number;
        # replacing its first frame element makes serial 1 unambiguously refer
        # to this documented SOLID, rather than interpreting 51 as an element
        # reference from the earlier error message.
        Element.delete([element_id], client=client)
    Element.create(
        {element_id: {
            "TYPE": "SOLID", "MATL": 1, "SECT": 0,
            "NODE": list(range(node_start, node_start + 8)),
        }},
        client=client,
    )


def _no_seeds() -> List[SeedStep]:
    """Tiers that need nothing beyond the base model."""
    return []


# --------------------------------------------------------------------------
# Tier: core — the baseline proven live on 2026-07-26 (Civil 10/10, Gen 9/9).
# --------------------------------------------------------------------------


def _core_cases() -> List[Case]:
    return [
        Case(
            StructureGroup,
            {"NAME": "SG_CRUD"}, {"NAME": "SG_CRUD_2"},
            lambda p: p.get("NAME"), "SG_CRUD", "SG_CRUD_2",
            confirmed=True,
        ),
        Case(
            BoundaryGroup,
            {"NAME": "BG_CRUD"}, {"NAME": "BG_CRUD_2"},
            lambda p: p.get("NAME"), "BG_CRUD", "BG_CRUD_2",
            confirmed=True,
        ),
        Case(
            LoadGroup,
            {"NAME": "LG_CRUD"}, {"NAME": "LG_CRUD_2"},
            lambda p: p.get("NAME"), "LG_CRUD", "LG_CRUD_2",
            confirmed=True,
        ),
        Case(
            Node,
            {"X": 1.0, "Y": 2.0, "Z": 3.0}, {"X": 1.0, "Y": 2.0, "Z": 9.5},
            lambda p: p.get("Z"), 3.0, 9.5,
            item_id=101, confirmed=True,
        ),
        # Keyed by node id: node 2 is seeded and no case deletes it.
        Case(
            Skew,
            {"iMETHOD": 1, "ANGLE_X": 0, "ANGLE_Y": 0, "ANGLE_Z": 30},
            {"iMETHOD": 1, "ANGLE_X": 0, "ANGLE_Y": 0, "ANGLE_Z": 45},
            lambda p: p.get("ANGLE_Z"), 30, 45,
            item_id=2, confirmed=True,
        ),
        # /db/STLD renumbers: the server assigns NO sequentially rather than
        # honouring the "Assign" key, so this has to be the next free slot
        # after the two the seed creates.
        Case(
            StaticLoadCase,
            {"NAME": "CRUDCASE", "TYPE": "L", "DESC": "crud"},
            {"NAME": "CRUDCASE", "TYPE": "L", "DESC": "crud updated"},
            lambda p: p.get("DESC"), "crud", "crud updated",
            item_id=3, confirmed=True,
        ),
        # Loads reference LC_SCRATCH, which the seed creates and nothing deletes.
        Case(
            NodalLoad,
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "FZ": -10.0}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "FZ": -25.0}]},
            lambda p: p["ITEMS"][0].get("FZ"), -10.0, -25.0,
            item_id=2, confirmed=True,
        ),
        Case(
            BeamLoad,
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "CMD": "BEAM", "TYPE": "UNILOAD",
                        "DIRECTION": "GZ", "D": [0, 1, 0, 0], "P": [-5.0, -5.0, 0, 0]}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "CMD": "BEAM", "TYPE": "UNILOAD",
                        "DIRECTION": "GZ", "D": [0, 1, 0, 0], "P": [-8.0, -8.0, 0, 0]}]},
            lambda p: p["ITEMS"][0]["P"][0], -5.0, -8.0,
            confirmed=True,
        ),
        # CONSTRAINT must be exactly 7 characters (Dx Dy Dz Rx Ry Rz W). A
        # 6-character string is rejected with "[Error] Constraint Condition
        # has(have) been incorrectly entered." rather than being padded.
        Case(
            Constraint,
            {"ITEMS": [{"ID": 2, "CONSTRAINT": "1110000"}]},
            {"ITEMS": [{"ID": 2, "CONSTRAINT": "1111111"}]},
            lambda p: p["ITEMS"][0].get("CONSTRAINT"), "1110000", "1111111",
            item_id=2, confirmed=True,
        ),
        # Deletes itself, which is what lets the moving tier re-create the
        # code it needs. Framed by the manual as Civil-only; live-confirmed
        # 2026-07-29 to also answer on Gen NX — but per-CODE, not
        # unconditionally: "AASHTO STANDARD"/"AASHTO LRFD"/"EUROCODE"/"BS"
        # create fine on Gen, while "KOREA"/"CHINA"/"KSCE-LSD15" answer 201
        # with `[Error] ... Unavailable moving load code` there (confirmed
        # live; presumably a licensed-module gate per region code, not a
        # route-level restriction). Uses "AASHTO STANDARD"/"AASHTO LRFD" here
        # specifically so this case runs unmodified on both products — don't
        # swap back to a KR/CN code without re-splitting per product.
        Case(
            MovingLoadCode,
            {"CODE": "AASHTO STANDARD"}, {"CODE": "AASHTO LRFD"},
            lambda p: p.get("CODE"), "AASHTO STANDARD", "AASHTO LRFD",
            confirmed=True,
        ),
    ]


# --------------------------------------------------------------------------
# Tier: props — material / section sub-types.
# --------------------------------------------------------------------------


def _props_seeds() -> List[SeedStep]:
    """/db/TMAT links a creep/shrinkage record to a strength record *by name*,
    so both have to outlive the cases that exercise those two tables.

    ⚠️ /db/TDMT and /db/TDME do **not** share a code-name enum, and the two
    spell the *same* code differently. This cost a whole session on
    2026-07-26, when /db/TDMT looked broken because it was being fed
    /db/TDME's spellings.

        code          /db/TDMT ``CODE``     /db/TDME ``CODENAME``
        CEB-FIP 2010  "CEB_FIP_2010"        "CEB-FIP(2010)"
        CEB-FIP 1990  "CEB"                 "CEB-FIP(1990)"
        KDS 2016      "KDS_2016"            "KDS-2016"
        European      "EUROPEAN"            "European"

    /db/TDMT takes UNDERSCORED_UPPERCASE tokens; /db/TDME takes the
    human-readable display string. Both are documented correctly and in full
    by the official articles (see docs/live_verification_notes.md for the
    URLs) — the values we were probing with came from a bad transcription in
    the vendored manual copy, not from MIDASIT.

    ``"European"`` is accepted here and reads back as ``"EUROPEAN"``, so the
    match is case-insensitive; that is why this seed works despite not being
    spelled the official way.

    The two error strings are still diagnostic: "Wrong Field" means the code
    name is unknown, while "[Error] Time Dependent Material(...) input data
    contain errors" means the name was recognised but the code's companion
    fields are missing. Vary the *value* before the field names.
    """
    return [
        # Two records, because /db/TMAT's update has to switch TDMT_NAME to a
        # *different* creep/shrinkage record and both have to outlive the
        # /db/TDMT case, which deletes its own. Pointing the update at
        # TDMT_CRUD instead earned a "Wrong DB Name" on 2026-07-26 - a
        # self-inflicted violation of the "nothing a case deletes is another
        # case's prerequisite" rule three functions above.
        SeedStep("tdmt_seed", lambda c: TimeDependentMaterialCreepShrinkage.create(
            {1: {"NAME": "TD_SEED", "CODE": "European", "STR": 24000, "HU": 70,
                 "MSIZE": 0.2, "CTYPE": "RS", "AGE": 28},
             2: {"NAME": "TD_SEED_2", "CODE": "European", "STR": 30000, "HU": 65,
                 "MSIZE": 0.25, "CTYPE": "RS", "AGE": 28}}, client=c)),
        SeedStep("tdme_seed", lambda c: TimeDependentMaterialStrength.create(
            {1: {"NAME": "TD_SEED", "TYPE": "CODE", "CODENAME": "CEB-FIP(2010)",
                 "STRENGTH": 24000}}, client=c)),
    ]


def _props_cases() -> List[Case]:
    return [
        # id 2: thickness 1 is the seeded one the plate element uses.
        Case(
            Thickness,
            {"NAME": "THK_CRUD", "TYPE": "VALUE", "bINOUT": False,
             "T_IN": 0.25, "T_OUT": 0, "O_VALUE": 0},
            {"NAME": "THK_CRUD", "TYPE": "VALUE", "bINOUT": False,
             "T_IN": 0.30, "T_OUT": 0, "O_VALUE": 0},
            lambda p: p.get("T_IN"), 0.25, 0.30,
            item_id=2, confirmed=True,
        ),
        # Keyed by element id.
        Case(
            ElementStiffnessScaleFactor,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "AREA_SF": 0.5, "ASY_SF": 1.0,
                        "ASZ_SF": 1.0, "IXX_SF": 1.0, "IYY_SF": 1.0, "IZZ_SF": 1.0,
                        "WGT_SF": 1.0}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "AREA_SF": 0.75, "ASY_SF": 1.0,
                        "ASZ_SF": 1.0, "IXX_SF": 1.0, "IYY_SF": 1.0, "IZZ_SF": 1.0,
                        "WGT_SF": 1.0}]},
            lambda p: p["ITEMS"][0].get("AREA_SF"), 0.5, 0.75,
            item_id=2, confirmed=True,
        ),
        # Resolved live 2026-07-26: /db/SECF is keyed by **section** id, not
        # element id. Posting under element 3 returned 200 with no error and
        # silently stored nothing; the identical body under section 1 round-
        # tripped. db/properties/section.py said "element id" and was wrong.
        Case(
            SectionStiffness,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "AREA_SF": 1.2, "IYY_SF": 1.0,
                        "IZZ_SF": 1.0, "WGT_SF": 1.0}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "AREA_SF": 1.4, "IYY_SF": 1.0,
                        "IZZ_SF": 1.0, "WGT_SF": 1.0}]},
            lambda p: p["ITEMS"][0].get("AREA_SF"), 1.2, 1.4,
            item_id=1, confirmed=True,
        ),
        Case(
            TaperedGroup,
            {"NAME": "TG_CRUD", "ELEMLIST": [2, 3], "ZVAR": "LINEAR", "YVAR": "LINEAR"},
            {"NAME": "TG_CRUD_2", "ELEMLIST": [2, 3], "ZVAR": "LINEAR", "YVAR": "LINEAR"},
            lambda p: p.get("NAME"), "TG_CRUD", "TG_CRUD_2",
            confirmed=True,
        ),
        # id 3: ids 1-2 are TD_SEED/TD_SEED_2, which /db/TMAT references by name.
        Case(
            TimeDependentMaterialCreepShrinkage,
            {"NAME": "TDMT_CRUD", "CODE": "European", "STR": 24000, "HU": 70,
             "MSIZE": 0.2, "CTYPE": "RS", "AGE": 28},
            {"NAME": "TDMT_CRUD", "CODE": "European", "STR": 24000, "HU": 60,
             "MSIZE": 0.2, "CTYPE": "RS", "AGE": 28},
            lambda p: p.get("HU"), 70, 60,
            item_id=3, confirmed=True, needs=("tdmt_seed",),
        ),
        Case(
            TimeDependentMaterialStrength,
            {"NAME": "TDME_CRUD", "TYPE": "CODE", "CODENAME": "CEB-FIP(2010)",
             "STRENGTH": 24000},
            {"NAME": "TDME_CRUD", "TYPE": "CODE", "CODENAME": "CEB-FIP(2010)",
             "STRENGTH": 30000},
            lambda p: p.get("STRENGTH"), 24000, 30000,
            item_id=2, confirmed=True, needs=("tdme_seed",),
        ),
        # Keyed by material id (the manual's example keys it "2", a material
        # number, not a running id). Material 1 is the seeded C24.
        Case(
            TimeDependentMaterialLink,
            {"TDMT_NAME": "TD_SEED", "TDME_NAME": "TD_SEED"},
            {"TDMT_NAME": "TD_SEED_2", "TDME_NAME": "TD_SEED"},
            lambda p: p.get("TDMT_NAME"), "TD_SEED", "TD_SEED_2",
            item_id=1, confirmed=True, needs=("tdmt_seed", "tdme_seed"),
        ),
    ]


# --------------------------------------------------------------------------
# Tier: boundary — springs and links.
# --------------------------------------------------------------------------


def _boundary_seeds() -> List[SeedStep]:
    """/db/GSPR assigns a general spring *type* by name, and the update step
    has to switch to a second one, so two survive the tier."""
    return [
        SeedStep("spring_types", lambda c: GeneralSpringType.create(
            {
                1: {"NAME": "GS_SEED", "OPT_STIFFNESS": True,
                    "SPRING": [1000, 0, 0, 0, 0, 0, 500, 0, 0, 0, 0, 500,
                               0, 0, 0, 0, 0, 0, 0, 0, 0]},
                2: {"NAME": "GS_SEED_2", "OPT_STIFFNESS": True,
                    "SPRING": [2000, 0, 0, 0, 0, 0, 800, 0, 0, 0, 0, 800,
                               0, 0, 0, 0, 0, 0, 0, 0, 0]},
            },
            client=c)),
    ]


def _boundary_cases() -> List[Case]:
    # All nine confirmed live on Civil NX 2026 v2.1 (build 06/05/2026),
    # 2026-07-26 — 9/9 full round trips in the first run that exercised them.
    return [
        # Keyed by node id. LINEAR uses SDR/F_S; COMP/TENS use STIFF/DIR/DV
        # and MULTI uses FUNCTION/DIR/DV instead (corrected 2026-08-27; see
        # PointSpringItem's docstring -- not exercised by this LINEAR case).
        Case(
            PointSpring,
            {"ITEMS": [{"ID": 1, "TYPE": "LINEAR", "GROUP_NAME": "",
                        "SDR": [1000, 500, 500, 0, 0, 0],
                        "F_S": [False, False, False, False, False, False]}]},
            {"ITEMS": [{"ID": 1, "TYPE": "LINEAR", "GROUP_NAME": "",
                        "SDR": [2000, 500, 500, 0, 0, 0],
                        "F_S": [False, False, False, False, False, False]}]},
            lambda p: p["ITEMS"][0]["SDR"][0], 1000, 2000,
            item_id=2, confirmed=True,
        ),
        # id 3: ids 1-2 are the seeded types /db/GSPR references by name.
        Case(
            GeneralSpringType,
            {"NAME": "GS_CRUD", "OPT_STIFFNESS": True,
             "SPRING": [1500, 0, 0, 0, 0, 0, 600, 0, 0, 0, 0, 600,
                        0, 0, 0, 0, 0, 0, 0, 0, 0]},
            {"NAME": "GS_CRUD_2", "OPT_STIFFNESS": True,
             "SPRING": [1500, 0, 0, 0, 0, 0, 600, 0, 0, 0, 0, 600,
                        0, 0, 0, 0, 0, 0, 0, 0, 0]},
            lambda p: p.get("NAME"), "GS_CRUD", "GS_CRUD_2",
            item_id=3, confirmed=True, needs=("spring_types",),
        ),
        Case(
            GeneralSpringSupport,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "TYPE_NAME": "GS_SEED"}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "TYPE_NAME": "GS_SEED_2"}]},
            lambda p: p["ITEMS"][0].get("TYPE_NAME"), "GS_SEED", "GS_SEED_2",
            item_id=3, confirmed=True, needs=("spring_types",),
        ),
        # The next three all use the free 21/22 node pair and each deletes
        # itself before the next runs — a node can't carry an elastic link, a
        # rigid link and a linear constraint at once.
        Case(
            ElasticLink,
            {"NODE": [21, 22], "LINK": "GEN", "ANGLE": 0,
             "SDR": [1000, 500, 500, 0, 0, 0],
             "R_S": [False, False, False, False, False, False],
             "bSHEAR": False, "DR": [0, 0]},
            {"NODE": [21, 22], "LINK": "GEN", "ANGLE": 0,
             "SDR": [2000, 500, 500, 0, 0, 0],
             "R_S": [False, False, False, False, False, False],
             "bSHEAR": False, "DR": [0, 0]},
            lambda p: p["SDR"][0], 1000, 2000,
            confirmed=True,
        ),
        # Keyed by *master* node id, not a running serial.
        Case(
            RigidLink,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "DOF": 111111, "S_NODE": [22]}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "DOF": 110001, "S_NODE": [22]}]},
            lambda p: p["ITEMS"][0].get("DOF"), 111111, 110001,
            item_id=21, confirmed=True,
        ),
        Case(
            LinearConstraint,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "SLAVE_TYPE": "111000", "TYPE": "EX",
                        "SLAVES": [{"NODE_KEY": 21, "COEFF": 1.0}]}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "SLAVE_TYPE": "111000", "TYPE": "EX",
                        "SLAVES": [{"NODE_KEY": 21, "COEFF": 0.5}]}]},
            lambda p: p["ITEMS"][0]["SLAVES"][0].get("COEFF"), 1.0, 0.5,
            item_id=22, confirmed=True,
        ),
        # Keyed by element id. FLAG_I/FLAG_J are 7-char [Fx,Fy,Fz,Mx,My,Mz,Mb].
        Case(
            BeamEndRelease,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "bVALUE": False,
                        "FLAG_I": "0000100", "VALUE_I": [0, 0, 0, 0, 0, 0, 0],
                        "FLAG_J": "0000000", "VALUE_J": [0, 0, 0, 0, 0, 0, 0]}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "bVALUE": False,
                        "FLAG_I": "0000100", "VALUE_I": [0, 0, 0, 0, 0, 0, 0],
                        "FLAG_J": "0000100", "VALUE_J": [0, 0, 0, 0, 0, 0, 0]}]},
            lambda p: p["ITEMS"][0].get("FLAG_J"), "0000000", "0000100",
            item_id=2, confirmed=True,
        ),
        # TYPE="ELEMENT" is the ECS form: no RGDXi/RGDXj.
        Case(
            BeamEndOffset,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "TYPE": "ELEMENT",
                        "RGDYi": 0.11, "RGDZi": 0.12, "RGDYj": 0.21, "RGDZj": 0.22}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "TYPE": "ELEMENT",
                        "RGDYi": 0.15, "RGDZi": 0.12, "RGDYj": 0.21, "RGDZj": 0.22}]},
            lambda p: p["ITEMS"][0].get("RGDYi"), 0.11, 0.15,
            item_id=3, confirmed=True,
        ),
        # Element 4 is the seeded plate; ELEM_TYPE has to match it.
        Case(
            SurfaceSpring,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "ELEM_TYPE": "PLANAR(FACE)",
                        "SPRING_TYPE": 0, "MODULUS": 500}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "", "ELEM_TYPE": "PLANAR(FACE)",
                        "SPRING_TYPE": 0, "MODULUS": 800}]},
            lambda p: p["ITEMS"][0].get("MODULUS"), 500, 800,
            item_id=4, confirmed=True,
        ),
    ]


# --------------------------------------------------------------------------
# Tier: static — the rest of ch06, plus ch07 element/nodal temperature.
# --------------------------------------------------------------------------


def _static_cases() -> List[Case]:
    return [
        # Node 1 is the constrained support, which is what a specified
        # displacement needs. VALUES is [Dx,Dy,Dz,Rx,Ry,Rz] in the local CS.
        Case(
            SpecifiedDisplacement,
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "",
                        "VALUES": [{"OPT_FLAG": True, "DISPLACEMENT": 0.01},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0}]}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "",
                        "VALUES": [{"OPT_FLAG": True, "DISPLACEMENT": 0.02},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0},
                                   {"OPT_FLAG": False, "DISPLACEMENT": 0}]}]},
            lambda p: p["ITEMS"][0]["VALUES"][0].get("DISPLACEMENT"), 0.01, 0.02,
            item_id=1, confirmed=True,
        ),
        Case(
            LoadsToMass,
            {"DIR": "XYZ", "bNODAL": True, "bBEAM": True, "bFLOOR": False,
             "bPRES": False, "GRAV": 9.806,
             "vLC": [{"LCNAME": "LC_SCRATCH", "FACTOR": 1.0}]},
            {"DIR": "XYZ", "bNODAL": True, "bBEAM": True, "bFLOOR": False,
             "bPRES": False, "GRAV": 9.806,
             "vLC": [{"LCNAME": "LC_SCRATCH", "FACTOR": 0.5}]},
            lambda p: p["vLC"][0].get("FACTOR"), 1.0, 0.5,
            confirmed=True,
        ),
        Case(
            NodalBodyForce,
            {"LCNAME": "LC_SCRATCH", "OPT_USE_GROUP": False, "KEY_NODE_ITEMS": [2, 3],
             "OPT_NODAL_MASS": True, "OPT_LOAD_TO_MASS": False, "OPT_STRUCT_MASS": True,
             "X": 1.0, "Y": 0, "Z": 0},
            {"LCNAME": "LC_SCRATCH", "OPT_USE_GROUP": False, "KEY_NODE_ITEMS": [2, 3],
             "OPT_NODAL_MASS": True, "OPT_LOAD_TO_MASS": False, "OPT_STRUCT_MASS": True,
             "X": 2.0, "Y": 0, "Z": 0},
            lambda p: p.get("X"), 1.0, 2.0,
            confirmed=True,
        ),
        Case(
            FloorLoadType,
            {"NAME": "FL_CRUD", "DESC": "",
             "ITEM": [{"LCNAME": "LC_SCRATCH", "FLOOR_LOAD": -5.0,
                       "OPT_SUB_BEAM_WEIGHT": False}]},
            {"NAME": "FL_CRUD", "DESC": "",
             "ITEM": [{"LCNAME": "LC_SCRATCH", "FLOOR_LOAD": -8.0,
                       "OPT_SUB_BEAM_WEIGHT": False}]},
            lambda p: p["ITEM"][0].get("FLOOR_LOAD"), -5.0, -8.0,
            confirmed=True,
        ),
        # The manual spells ELEM_TYPE "Plate/PlaneStress(Face)" in its worked
        # example and "Plate/Plane Stress (Face)" in its Specifications prose.
        # Both are accepted (checked 2026-07-26 on v2.2), so the inconsistency
        # is cosmetic. An earlier note here claimed the unspaced form was "the
        # one the server accepts" - that was inferred from this case passing,
        # without ever sending the spaced form. Don't infer an enum from one
        # value working.
        Case(
            PressureLoadType,
            {"NAME": "PL_CRUD", "DESC": "", "ELEM_TYPE": "Plate/PlaneStress(Face)",
             "PRESSURE_LOAD_ITEMS": [{"LOADCASENAME": "LC_SCRATCH",
                                      "LOADTYPE": "Uniform", "LOAD_P1": -20}]},
            {"NAME": "PL_CRUD", "DESC": "", "ELEM_TYPE": "Plate/PlaneStress(Face)",
             "PRESSURE_LOAD_ITEMS": [{"LOADCASENAME": "LC_SCRATCH",
                                      "LOADTYPE": "Uniform", "LOAD_P1": -30}]},
            lambda p: p["PRESSURE_LOAD_ITEMS"][0].get("LOAD_P1"), -20, -30,
            confirmed=True,
        ),
        # Keyed by element id — 4 is the seeded plate.
        #
        # ⚠️ DIRECTION is "LZ", not the documented default "NORMAL". On a PLATE
        # with FACE_EDGE_TYPE="FACE", "NORMAL" is rejected ("[Error] Errors
        # detected in Pressure Loads Data.(Item:Load Direction)") and omitting
        # DIRECTION fails the same way, so the default is a trap. Verified
        # 2026-07-26: LZ / LX / GZ / VECTOR all work.
        Case(
            PressureLoad,
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "",
                        "CMD": "PRES", "ELEM_TYPE": "PLATE",
                        "FACE_EDGE_TYPE": "FACE", "DIRECTION": "LZ",
                        "EDGE_FACE": 1,
                        "FORCES": [-10.0, -10.0, -10.0, -10.0]}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "",
                        "CMD": "PRES", "ELEM_TYPE": "PLATE",
                        "FACE_EDGE_TYPE": "FACE", "DIRECTION": "LZ",
                        "EDGE_FACE": 1,
                        "FORCES": [-20.0, -20.0, -20.0, -20.0]}]},
            lambda p: p["ITEMS"][0]["FORCES"][0], -10.0, -20.0,
            item_id=4, confirmed=True,
        ),
        # ch07: element and nodal temperature, the two temperature loads a
        # normal modelling script actually writes.
        Case(
            ElementTemperature,
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "", "TEMP": 35}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "", "TEMP": 20}]},
            lambda p: p["ITEMS"][0].get("TEMP"), 35, 20,
            item_id=1, confirmed=True,
        ),
        Case(
            NodalTemperature,
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "", "TEMPER": -3}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "", "TEMPER": 5}]},
            lambda p: p["ITEMS"][0].get("TEMPER"), -3, 5,
            item_id=3, confirmed=True,
        ),
        # Un-quarantined 2026-07-29 after 15+ crash reproductions across both
        # products led to the actual root cause: the server crashes when
        # NMAS's optional rmX/rmY/rmZ fields are omitted, and doesn't when
        # they're sent explicitly (even as 0.0). NodalMass.create()/.update()
        # now fill them in automatically, so this case - which posts through
        # those methods without ever setting them - exercises the fix
        # directly instead of triggering the defect. Confirmed as a clean
        # 9/9 static-tier round trip on Gen NX the same day. See
        # docs/live_verification_notes.md for the full reproduction history.
        Case(
            NodalMass,
            {"mX": 1.0, "mY": 1.0, "mZ": 1.0},
            {"mX": 1.0, "mY": 1.0, "mZ": 2.0},
            lambda p: p.get("mZ"), 1.0, 2.0,
            # Node 3 is part of BASE_MODEL_STEPS.  Do not duplicate it as a
            # case setup: the npm harness rightly refuses setup POSTs that
            # would overwrite a shared base-model record.
            item_id=3, confirmed=True,
        ),
    ]


# --------------------------------------------------------------------------
# Tier: stage — construction stages and what attaches to them.
# --------------------------------------------------------------------------


def _stage_seeds() -> List[SeedStep]:
    """Groups are referenced by *name* by /db/STAG, so their ids don't matter
    and the core tier's group cases can't interfere.

    The seeded stage deliberately activates nothing: a structure group can
    only be activated once across the whole stage sequence, so leaving it
    empty keeps SG_SEED free for the /db/STAG case below.
    """
    def _groups(c: MidasClient) -> None:
        StructureGroup.create({2: {"NAME": "SG_SEED"}}, client=c)
        BoundaryGroup.create({2: {"NAME": "BG_SEED"}}, client=c)
        LoadGroup.create({1: {"NAME": "LG_SEED"}}, client=c)

    return [
        SeedStep("groups", _groups),
        SeedStep("stage_1", lambda c: ConstructionStage.create(
            {1: {"NAME": "CS_SEED", "DURATION": 5, "bSV_RSLT": True,
                 "bSV_STEP": False, "bLOAD_STEP": False, "ADD_STEP": []}}, client=c)),
    ]


def _stage_cases() -> List[Case]:
    return [
        # id 2: stage 1 is CS_SEED, which /db/TMLD and /db/CRPC attach to.
        Case(
            ConstructionStage,
            {"NAME": "CS_CRUD", "DURATION": 10, "bSV_RSLT": True, "bSV_STEP": False,
             "bLOAD_STEP": False, "ADD_STEP": [],
             "ACT_ELEM": [{"GRUP_NAME": "SG_SEED", "AGE": 10}],
             "ACT_BNGR": [{"BNGR_NAME": "BG_SEED", "POS": "DEFORMED"}],
             "ACT_LOAD": [{"LOAD_NAME": "LG_SEED", "DAY": "FIRST"}]},
            {"NAME": "CS_CRUD", "DURATION": 20, "bSV_RSLT": True, "bSV_STEP": False,
             "bLOAD_STEP": False, "ADD_STEP": [],
             "ACT_ELEM": [{"GRUP_NAME": "SG_SEED", "AGE": 10}],
             "ACT_BNGR": [{"BNGR_NAME": "BG_SEED", "POS": "DEFORMED"}],
             "ACT_LOAD": [{"LOAD_NAME": "LG_SEED", "DAY": "FIRST"}]},
            lambda p: p.get("DURATION"), 10, 20,
            item_id=2, confirmed=True, needs=("groups",),
        ),
        # Keyed by construction stage id.
        Case(
            TimeLoadConstructionStage,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "LG_SEED", "DAY": 35}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "LG_SEED", "DAY": 25}]},
            lambda p: p["ITEMS"][0].get("DAY"), 35, 25,
            item_id=1, confirmed=True, needs=("groups", "stage_1"),
        ),
        Case(
            CreepCoefficientConstructionStage,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "LG_SEED", "CREEP": 1.2}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "LG_SEED", "CREEP": 1.5}]},
            lambda p: p["ITEMS"][0].get("CREEP"), 1.2, 1.5,
            item_id=1, confirmed=True, needs=("groups", "stage_1"),
        ),
        # Keyed by node id. Civil NX only as of 2026-07-29 — see
        # CamberConstructionStage's docstring.
        Case(
            CamberConstructionStage,
            {"DEFORM": 0.0, "USER": 0.17},
            {"DEFORM": 0.0, "USER": 0.28},
            lambda p: p.get("USER"), 0.17, 0.28,
            item_id=3, products=("civil",), confirmed=True, needs=("stage_1",),
        ),
    ]


# --------------------------------------------------------------------------
# Tier: moving — the moving-load chain, now AASHTO LRFD fixtures throughout
# (MVCD "AASHTO LRFD", vehicles keyed to "AASHTO-LRFD"/HL-93). Was
# Korea-standard (MVCD "KOREA", vehicles keyed to "KS-RB") through
# 2026-07-29: live-tested that day, /db/MVCD itself creates fine on Gen for
# "AASHTO STANDARD"/"AASHTO LRFD"/"EUROCODE"/"BS" but answers `[Error] ...
# Unavailable moving load code` for "KOREA"/"CHINA"/"KSCE-LSD15" —
# presumably a licensed-module gate per region code, not a route-level
# restriction. Rebuilt 2026-07-30 around AASHTO LRFD/HL-93 after
# cross-checking this exact fixture shape against a real production Civil
# NX arch-bridge model's live AASHTO LRFD data (see
# docs/live_verification_notes.md) — field-for-field identical to what a
# real bridge project stores, not an invented example. Confirmed live on
# Gen NX too, 2026-08-17 (batch 11b) -- the identical fixture (LLAN/MVHL/
# MVHC/MVLD) passes clean, same as the 32-endpoint ch08 mirror finding
# predicted. `products` widened to both, `confirmed` left as-is (was
# already True from the Civil confirmation).
# --------------------------------------------------------------------------


def _moving_seeds() -> List[SeedStep]:
    """Rebuilds the code the core tier's /db/MVCD case deleted, then the lane
    and vehicle that /db/MVLD and /db/MVHC reference by name.

    ⚠️ Do not send ``VEH_DEFAULT: {}``. Every one of its fields is documented
    as optional, but an empty object makes ``/db/MVHL`` silently no-op —
    ``{"message": ""}``, no error, and a following GET shows nothing was
    saved. Verified live; see docs/live_verification_notes.md.

    ⚠️ With ``MVCD.CODE="AASHTO LRFD"``, ``LineLaneItem``'s ``CENT_F`` must be
    a nonzero value in (0, 1) — omitting it (or leaving the field's own
    documented default of 0) is rejected server-side with "Centrifugal
    Force ( 0.0 < Value < 1.0)". See ``LineLaneItem``'s docstring in
    ``db/moving_loads.py``, independently reconfirmed against a real
    production model's own data (``CENT_F: 0.5``) on 2026-07-30.
    """
    return [
        SeedStep("mvcd", lambda c: MovingLoadCode.create({1: {"CODE": "AASHTO LRFD"}}, client=c)),
        SeedStep("lane", lambda c: TrafficLineLanes.create(
            {1: {"COMMON": {"LL_NAME": "LL_SEED", "LOAD_DIST": "LANE", "GROUP_NAME": "",
                            "SKEW_START": 0, "SKEW_END": 0, "MOVING": "BOTH",
                            "WHEEL_SPACE": 1.8, "WIDTH": 3, "OPT_AUTO_LANE": False},
                 "LANE_ITEMS": [{"ELEM": 2, "ECC": 0, "CENT_F": 0.5},
                                {"ELEM": 3, "ECC": 0, "CENT_F": 0.5}]}},
            client=c)),
        SeedStep("vehicle", lambda c: Vehicles.create(
            {1: {"MVLD_CODE": 2, "VEHICLE_LOAD_NAME": "HL93TRK_SEED",
                 "VEHICLE_LOAD_NUM": 1, "VEHICLE_TYPE_NAME": "HL-93TRK",
                 "STANDARD_CODE": "AASHTO-LRFD",
                 "VEH_DEFAULT": {"DYN_LOAD_ALLOWANCE": 33, "CENT_F": False}}},
            client=c)),
    ]


def _moving_cases() -> List[Case]:
    both_products = ("civil", "gen")  # confirmed live on Gen too, 2026-08-17 -- see tier comment
    return [
        # id 2: lane 1 is LL_SEED, which the /db/MVLD case references.
        Case(
            TrafficLineLanes,
            {"COMMON": {"LL_NAME": "LL_CRUD", "LOAD_DIST": "LANE", "GROUP_NAME": "",
                        "SKEW_START": 0, "SKEW_END": 0, "MOVING": "BOTH",
                        "WHEEL_SPACE": 1.8, "WIDTH": 3, "OPT_AUTO_LANE": False},
             "LANE_ITEMS": [{"ELEM": 2, "ECC": 0.0, "CENT_F": 0.5},
                            {"ELEM": 3, "ECC": 0.0, "CENT_F": 0.5}]},
            {"COMMON": {"LL_NAME": "LL_CRUD", "LOAD_DIST": "LANE", "GROUP_NAME": "",
                        "SKEW_START": 0, "SKEW_END": 0, "MOVING": "BOTH",
                        "WHEEL_SPACE": 1.8, "WIDTH": 3, "OPT_AUTO_LANE": False},
             "LANE_ITEMS": [{"ELEM": 2, "ECC": 0.5, "CENT_F": 0.5},
                            {"ELEM": 3, "ECC": 0.5, "CENT_F": 0.5}]},
            lambda p: p["LANE_ITEMS"][0].get("ECC"), 0.0, 0.5,
            item_id=2, products=both_products, confirmed=True, needs=("mvcd",),
        ),
        # id 2: vehicle 1 is the seeded HL-93TRK the class/case reference.
        #
        # VEHICLE_LOAD_NUM is the endpoint's branch discriminator, not a
        # count: 1 selects a standard DB vehicle (VEHICLE_TYPE_NAME +
        # STANDARD_CODE), 2 a user-defined one (USER_LOAD_TYPE +
        # LOAD_ITEMS). 3 and omission both answer Wrong Field. So this
        # fixture sends 1 because it is a standard HL-93TDM; sending 2 here
        # would build a user-defined vehicle and ignore the type name, which
        # is the branch working, not the product discarding data.
        #
        # An earlier version of this comment called that a silent corruption
        # alongside /db/CONS. Retracted 2026-09-03 after measuring both
        # branches on Civil NX — sent properly, branch 2 keeps every field.
        # What is worth knowing is the other way round: VEHICLE_TYPE_NAME is
        # not validated at all, so "NOT-A-VEHICLE" stores verbatim.
        # See docs/live_verification_notes.md and MD-16.
        Case(
            Vehicles,
            {"MVLD_CODE": 2, "VEHICLE_LOAD_NAME": "HL93TDM_CRUD",
             "VEHICLE_LOAD_NUM": 1, "VEHICLE_TYPE_NAME": "HL-93TDM",
             "STANDARD_CODE": "AASHTO-LRFD",
             "VEH_DEFAULT": {"DYN_LOAD_ALLOWANCE": 33, "CENT_F": False}},
            {"MVLD_CODE": 2, "VEHICLE_LOAD_NAME": "HL93TDM_CRUD",
             "VEHICLE_LOAD_NUM": 1, "VEHICLE_TYPE_NAME": "HL-93TDM",
             "STANDARD_CODE": "AASHTO-LRFD",
             "VEH_DEFAULT": {"DYN_LOAD_ALLOWANCE": 20, "CENT_F": False}},
            lambda p: p["VEH_DEFAULT"].get("DYN_LOAD_ALLOWANCE"), 33, 20,
            # /db/MVHL renumbers to the next free id, so id 2 is only id 2
            # while the ``vehicle`` seed holds id 1. The tier always ran that
            # seed, so Python never noticed the need was undeclared; the npm
            # harness seeds only what a case declares, and its POST landed
            # at id 1 (2026-09-16).
            item_id=2, products=both_products, confirmed=True,
            needs=("mvcd", "vehicle"),
        ),
        # VEHICLE_LD_NAMES takes the vehicle's VEHICLE_LOAD_NAME, not the
        # type name the manual's worked example shows — confirmed live
        # 2026-07-26 on the Korea-standard fixture this replaced.
        Case(
            VehicleClasses,
            {"VEHICLE_CLS_NAME": "VC_CRUD", "VEHICLE_LD_NAMES": ["HL93TRK_SEED"]},
            {"VEHICLE_CLS_NAME": "VC_CRUD_2", "VEHICLE_LD_NAMES": ["HL93TRK_SEED"]},
            lambda p: p.get("VEHICLE_CLS_NAME"), "VC_CRUD", "VC_CRUD_2",
            products=both_products, confirmed=True, needs=("mvcd", "vehicle"),
        ),
        Case(
            MovingLoadCase,
            {"LCNAME": "MV_CRUD", "DESC": "", "TYPE": 0,
             "DEFAULT": {"LANE_FACTOR_TYPE": 1,
                         "SCALE_FACTORS": [1.2, 1, 0.85, 0.65, 0.65, 0.65],
                         "COMB_OPTION": "INDEPENDENT",
                         "SUB_LOAD_DATAS": [{"VEHICLE_TYPE": "VL",
                                             "VEHICLE_NAME": "HL93TRK_SEED",
                                             "SCALE_FACTOR": 1.0,
                                             "MIN_LOADED_LANE": 1,
                                             "MAX_LOADED_LANE": 1,
                                             "LANE_NAMES": ["LL_SEED"]}]}},
            {"LCNAME": "MV_CRUD", "DESC": "", "TYPE": 0,
             "DEFAULT": {"LANE_FACTOR_TYPE": 1,
                         "SCALE_FACTORS": [1.2, 1, 0.85, 0.65, 0.65, 0.65],
                         "COMB_OPTION": "INDEPENDENT",
                         "SUB_LOAD_DATAS": [{"VEHICLE_TYPE": "VL",
                                             "VEHICLE_NAME": "HL93TRK_SEED",
                                             "SCALE_FACTOR": 0.8,
                                             "MIN_LOADED_LANE": 1,
                                             "MAX_LOADED_LANE": 1,
                                             "LANE_NAMES": ["LL_SEED"]}]}},
            lambda p: p["DEFAULT"]["SUB_LOAD_DATAS"][0].get("SCALE_FACTOR"), 1.0, 0.8,
            products=both_products, confirmed=True, needs=("mvcd", "lane", "vehicle"),
        ),
    ]


# --------------------------------------------------------------------------
# Tier: extras1 — batch 1 of the read-only-verified db.project/db.boundary
# endpoints (2026-08-16): project-wide singleton settings, name-only groups,
# and the general-link family. Deliberately excludes the 5 seismic-device
# endpoints (SDVI/SDVE/SDST/SDHY/SDIS) and DRLS — nested COMMON payloads and
# an empty-object payload respectively need their own fixture work first.
# --------------------------------------------------------------------------


def _extras1_seeds() -> List[SeedStep]:
    """Isolated from the core/boundary tiers' own nodes: a fresh 23-26 node
    quartet so this tier is runnable standalone. 23/24 back the NLNK/NLNK-M1
    *cases* (each overwrites the same pair, different element ids); 25/26
    back a general-link *seed* record that outlives those cases, for CGLP.

    ``pjcf_unlock``: a fresh document already carries a /db/PJCF record at
    id 1 (confirmed live 2026-08-16, Civil NX v2.2 build 08/14/2026 —
    ``ProjectInfo.items()`` returns a non-empty placeholder before any case
    runs). Its POST/DELETE are documented, but POST answers "Key Already
    Exist" for *any* id, not just 1, until that pre-existing record is
    deleted first -- a real singleton, same family as UNIT/STYP, just with
    DELETE as the unlock instead of being GET/PUT-only.

    ``fbld_seed``: /db/CO_F is keyed by a Floor Load Type id, and the base
    model seeds none, so a bare PUT 404s ("id 1 missing after update" --
    confirmed live 2026-08-16). /db/FBLD also renumbers to the next free
    slot rather than honouring the "Assign" key (same behaviour as
    /db/STLD, see the props tier's own note) -- it lands at id 1 in a
    fresh document regardless of the id requested here, so the CO_F case
    below targets id 1 to match.
    """
    return [
        SeedStep("extras1_nodes", lambda c: Node.create(
            {23: {"X": 0, "Y": 3 * BAY, "Z": 0}, 24: {"X": 0, "Y": 3 * BAY, "Z": HEIGHT},
             25: {"X": BAY, "Y": 3 * BAY, "Z": 0}, 26: {"X": BAY, "Y": 3 * BAY, "Z": HEIGHT}},
            client=c)),
        SeedStep("pjcf_unlock", lambda c: ProjectInfo.delete([1], client=c)),
        SeedStep("fbld_seed", lambda c: FloorLoadType.create(
            {1: {"NAME": "FL_SEED", "DESC": "",
                 "ITEM": [{"LCNAME": "LC_SCRATCH", "FLOOR_LOAD": -5.0,
                           "OPT_SUB_BEAM_WEIGHT": False}]}},
            client=c)),
        # NLLP's current manual SPG example includes DESC, TOTAL_WEIGHT, and
        # OPT_USE_MASS. Keep the seed complete so downstream general-link
        # cases are not blocked by an old abbreviated prerequisite.
        SeedStep("nllp_seed", lambda c: GeneralLinkProperty.create(
            {90: {"PROPERTY_NAME": "NLLP_SEED", "DESC": "Foundation Spring",
                  "APPLICATION_TYPE": "ELEMENT", "APPLICATION_TYPE_D": "SPG",
                  "TOTAL_WEIGHT": 0, "OPT_USE_MASS": False},
             91: {"PROPERTY_NAME": "NLLP_SEED_2", "DESC": "Foundation Spring",
                  "APPLICATION_TYPE": "ELEMENT", "APPLICATION_TYPE_D": "SPG",
                  "TOTAL_WEIGHT": 0, "OPT_USE_MASS": False}},
            client=c)),
        SeedStep("glink_seed", lambda c: GeneralLink.create(
            {90: {"NODE1": 25, "NODE2": 26, "PROP_NAME": "NLLP_SEED",
                  "REF_SYSTEM": 0, "BETA_ANGLE": 0}},
            client=c)),
    ]


def _extras1_cases() -> List[Case]:
    civil = ("civil",)
    return [
        Case(
            ProjectInfo,
            {"PROJECT": "CRUD_TEST", "USER": "crud"},
            {"PROJECT": "CRUD_TEST_2", "USER": "crud"},
            lambda p: p.get("PROJECT"), "CRUD_TEST", "CRUD_TEST_2",
            needs=("pjcf_unlock",), confirmed=True,
        ),
        # GET/PUT only, no POST/DELETE — the record already exists at id 1
        # in a fresh document (same pattern _seed_model relies on for Unit).
        # MASS must be 1 (Lumped) or 2 (Consistent) -- 0 answers "Wrong
        # Field" (confirmed live 2026-08-16; the manual's own Specifications
        # table calls it Optional with no stated default, but doesn't list 0
        # as a valid value either, only 1/2).
        Case(
            StructureType,
            {}, {"STYP": 0, "MASS": 1, "bMASSOFFSET": False, "bSELFWEIGHT": True,
                 "SMASS": 2, "GRAV": 9.806, "TEMP": 20, "bALIGNBEAM": False,
                 "bALIGNSLAB": False, "bROTRIGID": True},
            lambda p: p.get("TEMP"), None, 20,
            confirmed=True,
        ),
        Case(
            StructureTypeHyperS,
            {}, {"STYPE": "3D", "GRAV": 9.806, "TEMP": 0, "ALIGNBEAM": False,
                 "ALIGNSLAB": False,
                 "MASS_CONTROL": {"MASS_TYPE": "LUMPED", "MASS_POS": "CENTROID",
                                  "SELFWEIGHT": False}},
            lambda p: p.get("STYPE"), None, "3D",
            products=civil, confirmed=True,
        ),
        Case(
            TendonGroup,
            {"NAME": "TG_CRUD"}, {"NAME": "TG_CRUD_2"},
            lambda p: p.get("NAME"), "TG_CRUD", "TG_CRUD_2",
            confirmed=True,
        ),
        Case(
            NamedPlane,
            {"NAME": "NP_CRUD", "TYPE": 2, "COORD": 5.0},
            {"NAME": "NP_CRUD", "TYPE": 2, "COORD": 10.0},
            lambda p: p.get("COORD"), 5.0, 10.0,
            confirmed=True,
        ),
        # CO_M/CO_S/CO_T keyed by the material/section/thickness id they
        # colour — reuse the base seed's id-1 material/section/thickness.
        Case(
            MaterialColor,
            {}, {"W_R": 111, "W_G": 142, "W_B": 91, "bBLEMD": False, "FACT": 0.5},
            lambda p: p.get("W_R"), None, 111,
            item_id=1, confirmed=True,
        ),
        Case(
            SectionColor,
            {}, {"W_R": 111, "W_G": 142, "W_B": 91, "bBLEMD": False, "FACT": 0.5},
            lambda p: p.get("W_R"), None, 111,
            item_id=1, confirmed=True,
        ),
        Case(
            ThicknessColor,
            {}, {"W_R": 111, "W_G": 142, "W_B": 91, "bBLEMD": False, "FACT": 0.5},
            lambda p: p.get("W_R"), None, 111,
            item_id=1, confirmed=True,
        ),
        # CO_F is keyed by a Floor Load Type (/db/FBLD) id -- the fbld_seed
        # step provides one, landing at id 1 (FBLD renumbers, see the seed
        # docstring above). Its own "NAME" field is read-only, mirroring
        # the linked FBLD record's name (confirmed live 2026-08-16: a PUT
        # with NAME="FL_CRUD" echoed back "FL_SEED" unchanged) -- probe a
        # colour field instead, like CO_M/CO_S/CO_T.
        Case(
            FloorLoadColor,
            {}, {"NAME": "FL_CRUD", "WF_R": 166, "OPT_BLEND": True, "BLEND_FACTOR": 0.25},
            lambda p: p.get("WF_R"), None, 166,
            item_id=1, needs=("fbld_seed",), confirmed=True,
        ),
        # SPAN_BASE_ITEMS.length must be SPAN_LIST.length + 1 (one support
        # point per span boundary) -- confirmed live 2026-08-16 after a
        # 2-items/3-list mismatch answered "[Error] ... (Item:Number of
        # Spans)"; the manual's own Specifications table doesn't state this
        # relationship, only its JSON Schema shows two independently-typed
        # arrays.
        Case(
            Span,
            {"NAME": "SPAN_CRUD", "bEXACTSPAN": True, "DIRECTION": 0, "SECTTYPE": 0,
             "SPAN_LIST": [2.5, 5],
             "SPAN_BASE_ITEMS": [{"ELEM_KEY": 1, "SUPPORT": 1}, {"ELEM_KEY": 2, "SUPPORT": 1},
                                  {"ELEM_KEY": 3, "SUPPORT": 2}]},
            {"NAME": "SPAN_CRUD_2", "bEXACTSPAN": True, "DIRECTION": 0, "SECTTYPE": 0,
             "SPAN_LIST": [2.5, 5],
             "SPAN_BASE_ITEMS": [{"ELEM_KEY": 1, "SUPPORT": 1}, {"ELEM_KEY": 2, "SUPPORT": 1},
                                  {"ELEM_KEY": 3, "SUPPORT": 2}]},
            lambda p: p.get("NAME"), "SPAN_CRUD", "SPAN_CRUD_2",
            products=civil, confirmed=True,
        ),
        Case(
            GeneralLinkProperty,
            {"PROPERTY_NAME": "NLLP_CRUD", "DESC": "Foundation Spring",
             "APPLICATION_TYPE": "ELEMENT", "APPLICATION_TYPE_D": "SPG",
             "TOTAL_WEIGHT": 0, "OPT_USE_MASS": False},
            {"PROPERTY_NAME": "NLLP_CRUD_2", "DESC": "Foundation Spring",
             "APPLICATION_TYPE": "ELEMENT", "APPLICATION_TYPE_D": "SPG",
             "TOTAL_WEIGHT": 0, "OPT_USE_MASS": False},
            lambda p: p.get("PROPERTY_NAME"), "NLLP_CRUD", "NLLP_CRUD_2",
        ),
        Case(
            GeneralLink,
            {"NODE1": 23, "NODE2": 24, "PROP_NAME": "NLLP_SEED", "REF_SYSTEM": 0, "BETA_ANGLE": 0},
            {"NODE1": 23, "NODE2": 24, "PROP_NAME": "NLLP_SEED", "REF_SYSTEM": 0, "BETA_ANGLE": 15},
            lambda p: p.get("BETA_ANGLE"), 0, 15,
            needs=("nllp_seed", "extras1_nodes"),
        ),
        Case(
            GeneralLinkHyperS,
            {"PROP_NAME": "NLLP_SEED", "NODE1": 23, "NODE2": 24,
             "REF_SYSTEM": 0, "BETA_ANGLE": 0},
            {"PROP_NAME": "NLLP_SEED_2", "NODE1": 23, "NODE2": 24,
             "REF_SYSTEM": 0, "BETA_ANGLE": 15},
            lambda p: p.get("PROP_NAME"), "NLLP_SEED", "NLLP_SEED_2",
            item_id=2, products=civil, needs=("nllp_seed", "extras1_nodes"),
        ),
        Case(
            ChangeGeneralLinkProperty,
            {"GLINK_KEY": 90, "CHANGE_PROPERTY_NAME": "NLLP_SEED"},
            {"GLINK_KEY": 90, "CHANGE_PROPERTY_NAME": "NLLP_SEED_2"},
            lambda p: p.get("CHANGE_PROPERTY_NAME"), "NLLP_SEED", "NLLP_SEED_2",
            needs=("nllp_seed", "glink_seed"),
        ),
        # Element 4 is the base seed's plate.
        Case(
            PlateEndRelease,
            {"ITEMS": [{"ID": 1, "N1": [1, 1, 1, 0, 0], "N2": [0, 0, 0, 0, 0],
                        "N3": [0, 0, 0, 0, 0], "N4": [0, 0, 0, 0, 0]}]},
            {"ITEMS": [{"ID": 1, "N1": [1, 1, 1, 1, 0], "N2": [0, 0, 0, 0, 0],
                        "N3": [0, 0, 0, 0, 0], "N4": [0, 0, 0, 0, 0]}]},
            lambda p: p["ITEMS"][0].get("N1"), [1, 1, 1, 0, 0], [1, 1, 1, 1, 0],
            item_id=4, confirmed=True,
        ),
        Case(
            ForceDeformationFunction,
            {"NAME": "MLFC_CRUD", "TYPE": "FORCE", "SYMM": False,
             "ITEMS": [{"X": 0.0, "Y": 0.0}, {"X": 0.01, "Y": 100.0}, {"X": 0.02, "Y": 150.0}]},
            {"NAME": "MLFC_CRUD_2", "TYPE": "FORCE", "SYMM": False,
             "ITEMS": [{"X": 0.0, "Y": 0.0}, {"X": 0.01, "Y": 100.0}, {"X": 0.02, "Y": 150.0}]},
            lambda p: p.get("NAME"), "MLFC_CRUD", "MLFC_CRUD_2",
            confirmed=True,
        ),
        Case(
            PanelZoneEffect,
            {"OPT_OFFSET": False, "OFFS_FACTOR": 0.5, "OUTPUT_POSITION": 0},
            {"OPT_OFFSET": True, "OFFS_FACTOR": 0.75, "OUTPUT_POSITION": 0},
            lambda p: p.get("OFFS_FACTOR"), 0.5, 0.75,
            confirmed=True,
        ),
        # No DELETE (NO_DELETE_METHODS), keyed by node id — node 1 already
        # has a /db/CONS record, an unrelated table, so no collision.
        Case(
            ConstraintLabelDirection,
            {"DIR": 0}, {"DIR": 2},
            lambda p: p.get("DIR"), 0, 2,
            confirmed=True,
        ),
    ]


# --------------------------------------------------------------------------
# Tier: extras2 — batch 2 of the read-only-verified endpoints (2026-08-16):
# db.misc_loads in full, plus 3 of db.temperature_prestress's 10 (GTMP/STMP/
# BTMP; the other 7 are tendon/prestress endpoints, deferred with the
# seismic-device family from extras1). Payloads adapted from the manual's
# own end-to-end workflow example (docs/manual/11_DB_Settlement_Misc_Loads.md
# "End-to-End 워크플로우 예제"), which chains all 8 misc_loads endpoints
# through one consistent fixture — reused here almost verbatim.
# --------------------------------------------------------------------------


def _extras2_seeds() -> List[SeedStep]:
    """/db/SMPT renumbers to the next free slot rather than honouring the
    "Assign" key (confirmed live 2026-08-16, same family as /db/STLD and
    /db/FBLD) -- this seed's requested id 90 actually lands at id 1, which
    is why the SettlementGroup case below targets id 2, not 1.
    """
    return [
        SeedStep("smpt_seed", lambda c: SettlementGroup.create(
            {90: {"NAME": "SG_SEED", "SETTLE": 20, "ITEMS": [1, 2]}}, client=c)),
    ]


def _extras2_cases() -> List[Case]:
    return [
        Case(
            SettlementGroup,
            {"NAME": "SG_CRUD", "SETTLE": 25, "ITEMS": [1, 2]},
            {"NAME": "SG_CRUD_2", "SETTLE": 15, "ITEMS": [1, 2]},
            lambda p: p.get("NAME"), "SG_CRUD", "SG_CRUD_2",
            item_id=2, needs=("smpt_seed",), confirmed=True,
        ),
        # ST_GROUPS references the smpt_seed record by name, not the SMPT
        # case above (which deletes its own record before this would run).
        Case(
            SettlementLoadCase,
            {"NAME": "SLC_CRUD", "DESC": "", "FACTOR": 1.0, "MIN": 1, "MAX": 1,
             "ST_GROUPS": ["SG_SEED"]},
            {"NAME": "SLC_CRUD", "DESC": "", "FACTOR": 0.5, "MIN": 1, "MAX": 1,
             "ST_GROUPS": ["SG_SEED"]},
            lambda p: p.get("FACTOR"), 1.0, 0.5,
            needs=("smpt_seed",), confirmed=True,
        ),
        # Manual docstring: "Single global record — Assign key is always 1."
        Case(
            PreCompositeSection,
            {"LCNAME_ITEM": ["LC_SCRATCH"]}, {"LCNAME_ITEM": ["DL", "LC_SCRATCH"]},
            lambda p: p.get("LCNAME_ITEM"), ["LC_SCRATCH"], ["DL", "LC_SCRATCH"],
            products=("civil",), confirmed=True,
        ),
        Case(
            LoadSequenceNonlinear,
            {"LCNAME_ITEM": ["DL", "LC_SCRATCH"]}, {"LCNAME_ITEM": ["LC_SCRATCH", "DL"]},
            lambda p: p.get("LCNAME_ITEM"), ["DL", "LC_SCRATCH"], ["LC_SCRATCH", "DL"],
            confirmed=True,
        ),
        # ⚠️ Confirmed failing live 2026-08-16 (Civil NX v2.2, build
        # 08/14/2026) with the manual's own full canonical example
        # reproduced verbatim, AND with a bare {"NAME": "..."} payload --
        # both answer the identical "Wrong Field". Not a fixture bug this
        # checker can iterate past (same class of finding as /db/NLLP in
        # extras1): something about /db/WVLD's own preconditions is
        # undocumented, possibly a licensed offshore/marine module gate.
        # COEF/CHAR/PROF are Any-typed in the SDK either way -- no
        # Specifications table constrains those sub-objects further.
        Case(
            WaveLoad,
            {"NAME": "WV_CRUD", "DESC": "", "bSTLD": True, "bTHIS": False,
             "VERT_COORD": "GLOBAL_Z", "DENSITY": 10.05, "DEPTH": 30.0,
             "COEF": {"TYPE": "CONST",
                      "COEF_S": [{"GRUP": "", "DIA": 0.5, "DRAG_COEF_X": 0.0,
                                  "DRAG_COEF_Y": 0.65, "DRAG_COEF_Z": 0.65,
                                  "INER_COEF_X": 0.0, "INER_COEF_Y": 2.0, "INER_COEF_Z": 2.0}],
                      "COEF_R": [], "bOVER": False, "OVER_S": [], "OVER_R": []},
             "CHAR": {"THEORY": "AIRY", "FUNC": 1, "DIR": 0.0, "HEIGHT": 5.0,
                      "CHAR_TYPE": "PERIOD", "LENGTH": 0.0, "PERIOD": 8.0,
                      "K_FACTOR": 1.0, "SURFACE_V": 0.3, "BOTTOM_Y": 0.05},
             "PROF": {"CUR_DIR": 0.0, "CUR_FACTOR": 1.0, "GRID_DATA": []},
             "FLOOD_GRUP": [], "GROWTH": [], "GRID_X": 5, "GRID_Z": 5,
             "bSELFW": True, "bBUOYANT": True, "CREST": "MAX", "UNIT": "m",
             "INITAL_POS": 0.0, "STEP": 1.0, "POS": 5},
            {"NAME": "WV_CRUD_2", "DESC": "", "bSTLD": True, "bTHIS": False,
             "VERT_COORD": "GLOBAL_Z", "DENSITY": 10.05, "DEPTH": 30.0,
             "COEF": {"TYPE": "CONST",
                      "COEF_S": [{"GRUP": "", "DIA": 0.5, "DRAG_COEF_X": 0.0,
                                  "DRAG_COEF_Y": 0.65, "DRAG_COEF_Z": 0.65,
                                  "INER_COEF_X": 0.0, "INER_COEF_Y": 2.0, "INER_COEF_Z": 2.0}],
                      "COEF_R": [], "bOVER": False, "OVER_S": [], "OVER_R": []},
             "CHAR": {"THEORY": "AIRY", "FUNC": 1, "DIR": 0.0, "HEIGHT": 5.0,
                      "CHAR_TYPE": "PERIOD", "LENGTH": 0.0, "PERIOD": 8.0,
                      "K_FACTOR": 1.0, "SURFACE_V": 0.3, "BOTTOM_Y": 0.05},
             "PROF": {"CUR_DIR": 0.0, "CUR_FACTOR": 1.0, "GRID_DATA": []},
             "FLOOD_GRUP": [], "GROWTH": [], "GRID_X": 5, "GRID_Z": 5,
             "bSELFW": True, "bBUOYANT": True, "CREST": "MAX", "UNIT": "m",
             "INITAL_POS": 0.0, "STEP": 1.0, "POS": 5},
            lambda p: p.get("NAME"), "WV_CRUD", "WV_CRUD_2",
            products=("civil",),
        ),
        Case(
            IgnoreElementForLoadCase,
            {"ELEMENT": 1, "LCNAME": "DL", "OPT_IGNORE": True},
            {"ELEMENT": 1, "LCNAME": "DL", "OPT_IGNORE": False},
            lambda p: p.get("OPT_IGNORE"), True, False,
            confirmed=True,
        ),
        # Keyed by element id.
        Case(
            InitialForceGeometricStiffness,
            {"DIR": "GX", "INIT_FORCE": 100.0}, {"DIR": "GX", "INIT_FORCE": 200.0},
            lambda p: p.get("INIT_FORCE"), 100.0, 200.0,
            item_id=1, confirmed=True,
        ),
        Case(
            InitialForceControlData,
            {"bADDLC": False, "LCNAME": "DL", "bUSECOMB": False, "COMB_LIST": [],
             "bCHECK_GEOM_STIFF": True},
            {"bADDLC": True, "LCNAME": "DL", "bUSECOMB": False, "COMB_LIST": [],
             "bCHECK_GEOM_STIFF": True},
            lambda p: p.get("bADDLC"), False, True,
            confirmed=True,
        ),
        Case(
            InitialElementForce,
            {"ELEM_TYPE": "BEAM", "ELEM_KEY": 1,
             "ELEMENT_FORCES": [100, 0, 50, 0, 200, 0, -100, 0, -50, 0, -200, 0]},
            {"ELEM_TYPE": "BEAM", "ELEM_KEY": 1,
             "ELEMENT_FORCES": [150, 0, 50, 0, 200, 0, -100, 0, -50, 0, -200, 0]},
            lambda p: p.get("ELEMENT_FORCES"),
            [100, 0, 50, 0, 200, 0, -100, 0, -50, 0, -200, 0],
            [150, 0, 50, 0, 200, 0, -100, 0, -50, 0, -200, 0],
            confirmed=True,
        ),
        # Keyed by element id; element 1 is the base seed's beam.
        Case(
            TemperatureGradient,
            {"ITEMS": [{"ID": 1, "LCNAME": "DL", "TYPE": 1, "TZ": 5.0, "USE_HZ": False,
                        "HZ": 0.3, "TY": 3.0, "USE_HY": False, "HY": 0.3}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "DL", "TYPE": 1, "TZ": 8.0, "USE_HZ": False,
                        "HZ": 0.3, "TY": 3.0, "USE_HY": False, "HY": 0.3}]},
            lambda p: p["ITEMS"][0].get("TZ"), 5.0, 8.0,
            item_id=1, confirmed=True,
        ),
        Case(
            SystemTemperature,
            {"LCNAME": "DL", "GROUP_NAME": "", "TEMPER": 10.0},
            {"LCNAME": "DL", "GROUP_NAME": "", "TEMPER": 20.0},
            lambda p: p.get("TEMPER"), 10.0, 20.0,
            confirmed=True,
        ),
        # ⚠️ The manual flags this "MIDAS Civil NX 전용 기능" (Civil-only)
        # in prose, but it answered live on Gen NX too (confirmed
        # 2026-08-16, v2.1 build 08/14/2026) -- another documented-vs-
        # actual-routing mismatch, same pattern as the ch08/ch17
        # moving-load family. Left unrestricted (both products) here.
        Case(
            BeamSectionTemperature,
            {"ITEMS": [{"ID": 1, "LCNAME": "DL", "GROUP_NAME": "", "DIR": "LZ",
                        "REF": "Centroid", "NUM": 1, "bPSC": False,
                        "vSECTTMP": [{"TYPE": "ELEMENT", "VAL_B": 0.2, "VAL_H1": 0.1,
                                      "VAL_H2": 0.2, "VAL_T1": 3, "VAL_T2": 12.4}]}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "DL", "GROUP_NAME": "", "DIR": "LZ",
                        "REF": "Centroid", "NUM": 1, "bPSC": False,
                        "vSECTTMP": [{"TYPE": "ELEMENT", "VAL_B": 0.2, "VAL_H1": 0.1,
                                      "VAL_H2": 0.2, "VAL_T1": 5, "VAL_T2": 12.4}]}]},
            lambda p: p["ITEMS"][0]["vSECTTMP"][0].get("VAL_T1"), 3, 5,
            item_id=1, confirmed=True,
        ),
    ]


# --------------------------------------------------------------------------
# Tier: extras3 — batch 3 of the read-only-verified endpoints (2026-08-16):
# db.properties.* tractable subset (9 of its 15). Deferred: the 5
# fiber/inelastic-hinge endpoints (IMFM, EPMT, FIMP, IEHC, IEHG — need real
# stress-strain curve fixtures) and FIBR (depends on FIMP), same complexity
# class as extras1's deferred seismic-device family.
# --------------------------------------------------------------------------


def _extras3_seeds() -> List[SeedStep]:
    """VirtualBeam references two VSEC records by id -- seeded here rather
    than reusing the VirtualSection case's own record, which deletes itself.
    """
    return [
        SeedStep("vsec_seed", lambda c: VirtualSection.create(
            {90: {"NAME": "VS_SEED_1", "CENT_CALC_TYPE": 0, "CEN_PT_X": 0, "CEN_PT_Y": 0,
                  "CEN_PT_Z": 0, "NORMAL_X": 1, "NORMAL_Y": 0, "NORMAL_Z": 0,
                  "NODE_LIST": [5, 6, 7, 8], "ELEM_LIST": [4]},
             91: {"NAME": "VS_SEED_2", "CENT_CALC_TYPE": 0, "CEN_PT_X": 0, "CEN_PT_Y": 0,
                  "CEN_PT_Z": 0, "NORMAL_X": 1, "NORMAL_Y": 0, "NORMAL_Z": 0,
                  "NODE_LIST": [5, 6, 7, 8], "ELEM_LIST": [4]}},
            client=c)),
    ]


def _group_damping_payload(freq_mode_1: float) -> Dict[str, Any]:
    """Return chapter 04's complete `/db/GRDP` Request Body record."""
    return {
        "STIFF_COEF_DEFAULT": 0.0848826377636192,
        "MASS_COEF_DEFAULT": 0.04188790133333333,
        "OPT_CALC_WHEN_USED": True,
        "OPT_MASS_PROP_DEFAULT": True,
        "OPT_STIFF_PROP_DEFAULT": True,
        "DIRECT_CALC_MODE_DEFAULT": 1,
        "FREQ_PERIOD_MODE_DEFAULT": 0,
        "FREQ_MODE_1_DEFAULT": freq_mode_1,
        "FREQ_MODE_2_DEFAULT": 0.2,
        "PERIOD_MODE_1_DEFAULT": 0,
        "PERIOD_MODE_2_DEFAULT": 0,
        "DAMPING_MODE_1_DEFAULT": 0.06,
        "DAMPING_MODE_2_DEFAULT": 0.07,
        "bExistElement": True,
        "bExistStrain": True,
        "GROUP_DAMPING_ITEMS": [{
            "GROUP_TYPE": "MATERIAL", "GROUP_NAME": "1",
            "STIFF_COEF": 0.005787452574792216,
            "OPT_STIFF_PROP": True,
            "MASS_COEF": 0.06854383854545451,
            "OPT_MASS_PROP": True,
            "DIRECT_CALC_MODE": 1,
            "FREQ_PERIOD_MODE": 0,
            "FREQ_MODE_1": 0.5,
            "FREQ_MODE_2": 0.6,
            "PERIOD_MODE_1": 0,
            "PERIOD_MODE_2": 0,
            "DAMPING_RATIO_MODE": 0,
            "DAMPING_RATIO_MODE_1": 0.02,
            "DAMPING_RATIO_MODE_2": 0.02,
        }],
        "STRAIN_GROUP_ITEMS": [{
            "GROUP_TYPE": "MATERIAL", "GROUP_NAME": "1",
            "DAMPING_RATIO": 0.02,
        }],
        "ELEM_GROUP_PRIORITY": 0,
        "ELEM_VALUE_PRIORITY": 0,
        "STRAIN_GROUP_PRIORITY": 0,
        "STRAIN_VALUE_PRIORITY": 0,
    }


def _extras3_cases() -> List[Case]:
    return [
        # GROUP_NAME references the base seed's material by name ("C24").
        Case(
            # ⚠️ Confirmed failing live 2026-08-16 (Civil NX v2.2, build
            # 08/14/2026) even reproducing the manual's own canonical
            # example verbatim (GROUP_NAME as the material's numeric id
            # "1", not its name; the extra STIFF_COEF_DEFAULT/
            # MASS_COEF_DEFAULT/OPT_*_PROP_DEFAULT fields included) -- same
            # generic "Wrong Field" either way. Not resolved as a fixture
            # problem; same class of finding as /db/NLLP and /db/WVLD.
            GroupDamping,
            _group_damping_payload(0.1),
            _group_damping_payload(0.5),
            lambda p: p.get("FREQ_MODE_1_DEFAULT"), 0.1, 0.5,
            confirmed=True,
        ),
        # Keyed by material id; material 1 is the base seed's C24.
        Case(
            ChangeProperty,
            {"TYPE": "NSM", "H_VS": 0.15}, {"TYPE": "NSM", "H_VS": 0.20},
            lambda p: p.get("H_VS"), 0.15, 0.20,
            item_id=1, confirmed=True,
        ),
        Case(
            # ⚠️ Confirmed failing live 2026-08-16 (Civil NX v2.2, build
            # 08/14/2026) reproducing the manual's own Request Body example
            # verbatim (its 4-point vDAY array, not the 2-point one first
            # tried) -- same "Wrong Field". Same class of finding as
            # /db/NLLP, /db/WVLD, /db/GRDP.
            TimeDependentMaterialFunction,
            {"NAME": "CreepFunc_1", "FTYPE": "CREEP", "CTYPE": "CC", "SCALE": 1.0,
             "DESC": "", "vDAY": [{"DAY": 28, "VALUE": 0.5}, {"DAY": 90, "VALUE": 1.0},
                                   {"DAY": 365, "VALUE": 1.5}, {"DAY": 3650, "VALUE": 2.0}]},
            {"NAME": "CreepFunc_1", "FTYPE": "CREEP", "CTYPE": "CC", "SCALE": 1.2,
             "DESC": "", "vDAY": [{"DAY": 28, "VALUE": 0.5}, {"DAY": 90, "VALUE": 1.0},
                                   {"DAY": 365, "VALUE": 1.5}, {"DAY": 3650, "VALUE": 2.0}]},
            lambda p: p.get("SCALE"), 1.0, 1.2,
        ),
        # ⚠️ Confirmed failing live 2026-08-16 (Civil NX v2.2, build
        # 08/14/2026). Later /info evidence corrected RPSC to nested
        # MBARS[].MBAR_ITEMS[] (MD-40) and STRPSSM points to Y/Z (MD-38),
        # so these fixtures follow the live-corrected contracts rather than
        # the stale manual examples. Their worked examples key at ids
        # 401/9003 and describe "PSC/RC 단면" specifically -- our base
        # seed's section is a plain DBUSER rectangular column, which may not
        # carry a Section Manager reinforcement/stress-point slot at all.
        # Genuinely unresolved either way; not swept under a workaround.
        # Keyed by section id; section 1 is the base seed's column section.
        Case(
            SectionReinforcement,
            {"OPT_MBAR_J": False, "OPT_SBAR_J": False, "OPT_CRACKED": False,
             "SBAR_ITEMS": [{"OPT_DR": False}, {"OPT_DR": False}],
             "MBARS": [{"MBAR_ITEMS": [
                 {"IJ": "I", "NAME": "D25", "REF_Y": 0, "Y": 0,
                  "REF_Z": 1, "Z": 0.05, "NUM": 4, "SPACING": 0.15},
             ]}]},
            {"OPT_MBAR_J": False, "OPT_SBAR_J": False, "OPT_CRACKED": True,
             "SBAR_ITEMS": [{"OPT_DR": False}, {"OPT_DR": False}],
             "MBARS": [{"MBAR_ITEMS": [
                 {"IJ": "I", "NAME": "D25", "REF_Y": 0, "Y": 0,
                  "REF_Z": 1, "Z": 0.05, "NUM": 4, "SPACING": 0.15},
             ]}]},
            lambda p: p.get("OPT_CRACKED"), False, True,
            item_id=1,
        ),
        Case(
            SectionStressPoints,
            {"OPT_SAME_J": True, "POINT_SIZE_1": 2, "POINT_SIZE_2": 2,
             "POINT1": [{"Y": 0.00583, "Z": 0.00476}, {"Y": -0.00506, "Z": 0.00097}],
             "POINT2": [{"Y": 0.00583, "Z": 0.00476}, {"Y": -0.00506, "Z": 0.00097}]},
            {"OPT_SAME_J": True, "POINT_SIZE_1": 2, "POINT_SIZE_2": 2,
             "POINT1": [{"Y": 0.006, "Z": 0.00476}, {"Y": -0.00506, "Z": 0.00097}],
             "POINT2": [{"Y": 0.006, "Z": 0.00476}, {"Y": -0.00506, "Z": 0.00097}]},
            lambda p: p["POINT1"][0].get("Y"), 0.00583, 0.006,
            item_id=1, products=("civil",), confirmed=True,
        ),
        # Keyed by element id; element 4 is the base seed's plate.
        Case(
            PlateStiffnessScaleFactor,
            {"ITEMS": [{"ID": 1, "AXIAL_X": 0.8}]},
            {"ITEMS": [{"ID": 1, "AXIAL_X": 0.5}]},
            lambda p: p["ITEMS"][0].get("AXIAL_X"), 0.8, 0.5,
            item_id=4, confirmed=True,
        ),
        Case(
            VirtualSection,
            {"NAME": "VS_CRUD", "CENT_CALC_TYPE": 0, "CEN_PT_X": 0, "CEN_PT_Y": 0,
             "CEN_PT_Z": 0, "NORMAL_X": 1, "NORMAL_Y": 0, "NORMAL_Z": 0,
             "NODE_LIST": [5, 6, 7, 8], "ELEM_LIST": [4]},
            {"NAME": "VS_CRUD_2", "CENT_CALC_TYPE": 0, "CEN_PT_X": 0, "CEN_PT_Y": 0,
             "CEN_PT_Z": 0, "NORMAL_X": 1, "NORMAL_Y": 0, "NORMAL_Z": 0,
             "NODE_LIST": [5, 6, 7, 8], "ELEM_LIST": [4]},
            lambda p: p.get("NAME"), "VS_CRUD", "VS_CRUD_2",
            confirmed=True,
        ),
        # Keyed by element id; VSEC1/VSEC2 reference the vsec_seed records.
        Case(
            VirtualBeam,
            {"VSEC1": 90, "VSEC2": 91}, {"VSEC1": 91, "VSEC2": 90},
            lambda p: p.get("VSEC1"), 90, 91,
            item_id=1, needs=("vsec_seed",), confirmed=True,
        ),
        Case(
            EffectiveWidthScaleFactor,
            {"ITEMS": [{"ID": 1, "LYSCALE": 1.0, "ZTSCALE": 1.0, "ZBSCALE": 1.0, "bJ": False}]},
            {"ITEMS": [{"ID": 1, "LYSCALE": 0.8, "ZTSCALE": 1.0, "ZBSCALE": 1.0, "bJ": False}]},
            lambda p: p["ITEMS"][0].get("LYSCALE"), 1.0, 0.8,
            item_id=1, products=("civil",), confirmed=True,
        ),
    ]


# --------------------------------------------------------------------------
# Tier: extras4 — batch 4 of the read-only-verified endpoints (2026-08-16):
# db.load_combinations in full (8/8) -- all six LCOM-* endpoints share one
# payload shape (see LoadCombinationPayload's docstring in
# db/load_combinations.py), so this tier is nearly a copy-paste of one case
# six times over.
# --------------------------------------------------------------------------


def _extras4_seeds() -> List[SeedStep]:
    """Civil-only prerequisite for the manual-shaped seismic combination.

    The manual's ``ANAL=\"RS\"`` row names a Response Spectrum Load Case, not
    a static load case. Keep the two records in the language-neutral seed map
    too, so the npm harness can exercise the identical public API path.
    """
    def _response_spectrum_load_case(c: MidasClient) -> None:
        ResponseSpectrumFunction.create(
            BASE_MODEL_SEEDS["lcom_seismic_spfc"]["records"], client=c)
        ResponseSpectrumLoadCase.create(
            BASE_MODEL_SEEDS["lcom_seismic_splc"]["records"], client=c)

    return [
        SeedStep(
            "lcom_seismic_splc", _response_spectrum_load_case,
            products=("civil",),
        ),
    ]


def _extras4_cases() -> List[Case]:
    lcom_case = lambda resource, active, **kw: Case(  # noqa: E731
        resource,
        {"NAME": "LCOM_CRUD", "ACTIVE": active, "iTYPE": 0, "DESC": "",
         "vCOMB": [{"ANAL": "ST", "LCNAME": "DL", "FACTOR": 1.0}]},
        {"NAME": "LCOM_CRUD", "ACTIVE": active, "iTYPE": 0, "DESC": "",
         "vCOMB": [{"ANAL": "ST", "LCNAME": "DL", "FACTOR": 1.2}]},
        lambda p: p["vCOMB"][0].get("FACTOR"), 1.0, 1.2,
        **kw,
    )
    return [
        lcom_case(LoadCombinationGeneral, "ACTIVE", confirmed=True),
        lcom_case(LoadCombinationConcrete, "STRENGTH", confirmed=True),
        lcom_case(LoadCombinationSteel, "STRENGTH", confirmed=True),
        lcom_case(LoadCombinationSRC, "STRENGTH", confirmed=True),
        lcom_case(LoadCombinationCompositeSteelGirder, "STRENGTH", confirmed=True),
        # The Gen result is deliberately separate from Civil's manual-shaped
        # RS case below. Gen re-confirmed this documented static-member shape
        # on 2026-09-01; Civil has a different server-side type restriction.
        lcom_case(
            LoadCombinationSeismic, "ACTIVE", products=("gen",), confirmed=True,
            # Both harnesses build the shared scratch model, including DL,
            # before cases run. Re-seeding it would be a setup collision.
        ),
        # The manual's LCOM-SEISMIC examples name response-spectrum entries
        # with ANAL="RS". SPLC_LCOM_SEED is a real /db/SPLC record created
        # from that same manual-backed fixture before this case runs.
        Case(
            LoadCombinationSeismic,
            {"NAME": "LCOM_SEISMIC_RS", "ACTIVE": "ACTIVE", "iTYPE": 0,
             "DESC": "1.0RS", "vCOMB": [
                 {"ANAL": "RS", "LCNAME": "SPLC_LCOM_SEED", "FACTOR": 1.0},
             ]},
            {"NAME": "LCOM_SEISMIC_RS", "ACTIVE": "ACTIVE", "iTYPE": 0,
             "DESC": "1.2RS", "vCOMB": [
                 {"ANAL": "RS", "LCNAME": "SPLC_LCOM_SEED", "FACTOR": 1.2},
             ]},
            lambda p: p["vCOMB"][0].get("FACTOR"), 1.0, 1.2,
            products=("civil",), needs=("lcom_seismic_splc",),
            setup=(
                {"seed": "lcom_seismic_spfc"},
                {"seed": "lcom_seismic_splc"},
            ),
        ),
        Case(
            CuttingLine,
            {"NAME": "CUT_CRUD", "DIR": "NORMAL", "PT1X": 0, "PT1Y": 0, "PT1Z": 0,
             "PT2X": 1, "PT2Y": 0, "PT2Z": 0, "TYPE": 0},
            {"NAME": "CUT_CRUD_2", "DIR": "NORMAL", "PT1X": 0, "PT1Y": 0, "PT1Z": 0,
             "PT2X": 1, "PT2Y": 0, "PT2Z": 0, "TYPE": 0},
            lambda p: p.get("NAME"), "CUT_CRUD", "CUT_CRUD_2",
            confirmed=True,
        ),
        Case(
            PlateCuttingLineDiagram,
            {"NAME": "CLWP_CRUD", "DIR": "NORMAL", "PT1X": 0, "PT1Y": 0, "PT1Z": 0,
             "PT2X": 1, "PT2Y": 0, "PT2Z": 0, "PT3X": 0, "PT3Y": 1, "PT3Z": 0},
            {"NAME": "CLWP_CRUD_2", "DIR": "NORMAL", "PT1X": 0, "PT1Y": 0, "PT1Z": 0,
             "PT2X": 1, "PT2Y": 0, "PT2Z": 0, "PT3X": 0, "PT3Y": 1, "PT3Z": 0},
            lambda p: p.get("NAME"), "CLWP_CRUD", "CLWP_CRUD_2",
            confirmed=True,
        ),
    ]


# --------------------------------------------------------------------------
# Tier: extras5 — batch 5 of the read-only-verified endpoints (2026-08-16):
# 9 of db.dynamic_loads's 12 (THGC-M1/THOO-M1/THIS-M1, the Hyper-S variants
# with deeply-nested required control sub-objects, deferred). Building a
# real /db/SPLC also unblocks extras4's LCOM-SEISMIC on Civil, which
# rejects a plain "ST" combination and needs an "RS"-typed load case.
# --------------------------------------------------------------------------


def _extras5_seeds() -> List[SeedStep]:
    """SPFC/THFC (functions) and THIS (a time-history load case) are
    referenced by name from several sibling cases below, so each gets a
    persistent seed record distinct from its own tested case's record.

    All three (and THIS's own case) renumber to id 1 rather than honouring
    the "Assign" key requested here (id 90) -- same STLD/FBLD/SMPT family,
    confirmed live 2026-08-16. That's why the sibling cases in
    _extras5_cases() below target id 2, not 1.

    thfc_force_seed exists separately from thfc_seed because /db/THNL's
    FUNC_NAME requires a Force/Moment-type function (iTYPE=3/4) --
    confirmed live: referencing thfc_seed's Accel-type (iTYPE=2) function
    answers "Unknown Error", not a field-name problem.
    """
    return [
        SeedStep("spfc_seed", lambda c: ResponseSpectrumFunction.create(
            {90: {"NAME": "SPFC_SEED", "iTYPE": 2, "iMETHOD": 0, "SCALE": 1.0,
                  "GRAV": 9.806, "DRATIO": 0.05, "DESC": "",
                  "aFUNC": [{"PERIOD": 0.1, "VALUE": 0.5}, {"PERIOD": 0.5, "VALUE": 1.0},
                            {"PERIOD": 1.0, "VALUE": 0.3}]}},
            client=c)),
        SeedStep("thfc_seed", lambda c: TimeHistoryFunction.create(
            {90: {"NAME": "THFC_SEED", "DESC": "", "iTYPE": 2, "GRAV": 9.806,
                  "FUNCTYPE": 1, "iMETHOD": 0, "SCALE": 1.0,
                  "aFUNCDATA": [{"TIME": 0, "VALUE": 0}, {"TIME": 0.1, "VALUE": 0.5},
                                {"TIME": 0.2, "VALUE": 1.0}]}},
            client=c)),
        SeedStep("thfc_force_seed", lambda c: TimeHistoryFunction.create(
            {91: {"NAME": "THFC_FORCE_SEED", "DESC": "", "iTYPE": 3, "GRAV": 9.806,
                  "FUNCTYPE": 1, "iMETHOD": 0, "SCALE": 1.0,
                  "aFUNCDATA": [{"TIME": 0, "VALUE": 0}, {"TIME": 0.1, "VALUE": 0.5}]}},
            client=c)),
        SeedStep("this_seed", lambda c: TimeHistoryLoadCase.create(
            {90: {"COMMON": {"NAME": "THIS_SEED", "iATYPE": 1, "iAMETHOD": 1, "iTHTYPE": 1,
                             "ENDTIME": 30.0, "INC": 0.01, "iOUT": 1, "INITMETHOD": "INIT",
                             "INITLOAD": 0, "bDVA": False, "bKEEP": False, "iMDTYPE": 1},
                  "DALL": 0.05}},
            client=c)),
    ]


def _extras5_cases() -> List[Case]:
    return [
        # id 2: spfc_seed renumbers to id 1 (see seed docstring above).
        Case(
            ResponseSpectrumFunction,
            {"NAME": "SPFC_CRUD", "iTYPE": 2, "iMETHOD": 0, "SCALE": 1.0, "GRAV": 9.806,
             "DRATIO": 0.05, "DESC": "",
             "aFUNC": [{"PERIOD": 0.1, "VALUE": 0.5}, {"PERIOD": 0.5, "VALUE": 1.0},
                       {"PERIOD": 1.0, "VALUE": 0.3}]},
            {"NAME": "SPFC_CRUD", "iTYPE": 2, "iMETHOD": 0, "SCALE": 1.2, "GRAV": 9.806,
             "DRATIO": 0.05, "DESC": "",
             "aFUNC": [{"PERIOD": 0.1, "VALUE": 0.5}, {"PERIOD": 0.5, "VALUE": 1.0},
                       {"PERIOD": 1.0, "VALUE": 0.3}]},
            lambda p: p.get("SCALE"), 1.0, 1.2,
            item_id=2, needs=("spfc_seed",), confirmed=True,
        ),
        # aFUNCNAME references the spfc_seed record by name.  Keep every
        # field from the manual's no-damping Request Example: the old lean
        # fixture did not exercise the documented mode/combination shape and
        # produced an uninformative Gen-only Unknown Error.
        *[
            Case(
                ResponseSpectrumLoadCase,
                {"NAME": "SPLC_CRUD", "DIR": "XY", "ANGLE": 0, "SCALE": 1.0,
                 "PMFT": 1.0, "bDAMP": False, "INTERP": "LOG", "COMTYPE": "CQC",
                 "bADDSIGN": True, "iSIGNTYPE": 0, "bMODE": True,
                 "aFUNCNAME": ["SPFC_SEED"],
                 "aUSEMODE": [{"bUSE": True, "MSFACTOR": 1},
                              {"bUSE": True, "MSFACTOR": 1},
                              {"bUSE": True, "MSFACTOR": 1}]},
                {"NAME": "SPLC_CRUD", "DIR": "XY", "ANGLE": 0, "SCALE": 1.2,
                 "PMFT": 1.0, "bDAMP": False, "INTERP": "LOG", "COMTYPE": "CQC",
                 "bADDSIGN": True, "iSIGNTYPE": 0, "bMODE": True,
                 "aFUNCNAME": ["SPFC_SEED"],
                 "aUSEMODE": [{"bUSE": True, "MSFACTOR": 1},
                              {"bUSE": True, "MSFACTOR": 1},
                              {"bUSE": True, "MSFACTOR": 1}]},
                lambda p: p.get("SCALE"), 1.0, 1.2,
                needs=("spfc_seed",), products=products, confirmed=confirmed,
            )
            for products, confirmed in (
                (("civil",), True),
                (("gen",), True),
            )
        ],
        # ⚠️ The manual flags this "CIVIL NX 전용" (Civil-only) in prose,
        # matching db/dynamic_loads.py's own docstring note that it was
        # already found to answer on Gen NX too (empty-table route+/info
        # check, 2026-07-29) -- left unrestricted here to get a write-level
        # confirmation of that on both products, not just the read-level one.
        Case(
            TimeHistoryGlobalControl,
            {"GNT": 0, "ILT": 0, "aILL": [{"SLC": "DL", "SF": 1.0, "LCT": 1}],
             "IEPI": True, "NSTEP": 1, "bROT": False, "SNIO": 1, "bPCF": True,
             "MAXNS": 10, "MAXIT": 10, "bDN": True, "bFN": False, "bEN": False,
             "DN": 0.001, "FN": 0.001, "EN": 0.001, "bULSM": False, "ULSM": 5,
             "ENERGYRESULT": False, "SDVI": False, "SDVE": False, "SDST": False,
             "SDHY": False, "SDIS": False, "bMSSSTATUS": False},
            {"GNT": 0, "ILT": 0, "aILL": [{"SLC": "DL", "SF": 1.0, "LCT": 1}],
             "IEPI": True, "NSTEP": 2, "bROT": False, "SNIO": 1, "bPCF": True,
             "MAXNS": 10, "MAXIT": 10, "bDN": True, "bFN": False, "bEN": False,
             "DN": 0.001, "FN": 0.001, "EN": 0.001, "bULSM": False, "ULSM": 5,
             "ENERGYRESULT": False, "SDVI": False, "SDVE": False, "SDST": False,
             "SDHY": False, "SDIS": False, "bMSSSTATUS": False},
            lambda p: p.get("NSTEP"), 1, 2,
            confirmed=True,
        ),
        # "Linear Modal Transient" shape from the manual's own worked
        # example -- COMMON's iATYPE=1(Linear)/iAMETHOD=1(Modal) combo
        # needs the top-level "DALL" (modal damping) key alongside COMMON,
        # not itemized in the Specifications table itself.
        # id 2: this_seed renumbers to id 1 (see seed docstring above).
        Case(
            TimeHistoryLoadCase,
            {"COMMON": {"NAME": "THIS_CRUD", "iATYPE": 1, "iAMETHOD": 1, "iTHTYPE": 1,
                        "ENDTIME": 30.0, "INC": 0.01, "iOUT": 1, "INITMETHOD": "INIT",
                        "INITLOAD": 0, "bDVA": False, "bKEEP": False, "iMDTYPE": 1},
             "DALL": 0.05},
            {"COMMON": {"NAME": "THIS_CRUD", "iATYPE": 1, "iAMETHOD": 1, "iTHTYPE": 1,
                        "ENDTIME": 45.0, "INC": 0.01, "iOUT": 1, "INITMETHOD": "INIT",
                        "INITLOAD": 0, "bDVA": False, "bKEEP": False, "iMDTYPE": 1},
             "DALL": 0.05},
            lambda p: p["COMMON"].get("ENDTIME"), 30.0, 45.0,
            item_id=2, needs=("this_seed",), confirmed=True,
        ),
        # id 3: thfc_seed and thfc_force_seed renumber to ids 1 and 2.
        Case(
            TimeHistoryFunction,
            {"NAME": "THFC_CRUD", "DESC": "", "iTYPE": 2, "GRAV": 9.806, "FUNCTYPE": 1,
             "iMETHOD": 0, "SCALE": 1.0,
             "aFUNCDATA": [{"TIME": 0, "VALUE": 0}, {"TIME": 0.1, "VALUE": 0.5},
                           {"TIME": 0.2, "VALUE": 1.0}]},
            {"NAME": "THFC_CRUD", "DESC": "", "iTYPE": 2, "GRAV": 9.806, "FUNCTYPE": 1,
             "iMETHOD": 0, "SCALE": 1.5,
             "aFUNCDATA": [{"TIME": 0, "VALUE": 0}, {"TIME": 0.1, "VALUE": 0.5},
                           {"TIME": 0.2, "VALUE": 1.0}]},
            lambda p: p.get("SCALE"), 1.0, 1.5,
            item_id=3, needs=("thfc_seed", "thfc_force_seed"), confirmed=True,
        ),
        # NAME references the this_seed load case by name; FUNCX/Y/Z
        # reference the thfc_seed function by name.
        Case(
            GroundAcceleration,
            {"NAME": "THIS_SEED", "ANGLE": 0, "FUNCX": "THFC_SEED", "SCALEX": 1.0,
             "ATIMEX": 0, "FUNCY": "THFC_SEED", "SCALEY": 1.0, "ATIMEY": 0,
             "FUNCZ": "THFC_SEED", "SCALEZ": 1.0, "ATIMEZ": 0},
            {"NAME": "THIS_SEED", "ANGLE": 0, "FUNCX": "THFC_SEED", "SCALEX": 1.5,
             "ATIMEX": 0, "FUNCY": "THFC_SEED", "SCALEY": 1.0, "ATIMEY": 0,
             "FUNCZ": "THFC_SEED", "SCALEZ": 1.0, "ATIMEZ": 0},
            lambda p: p.get("SCALEX"), 1.0, 1.5,
            needs=("this_seed", "thfc_seed"), confirmed=True,
        ),
        # Keyed by node id; node 1 is the base seed's frame node. FUNC_NAME
        # must reference a Force/Moment-type function (thfc_force_seed,
        # iTYPE=3) -- the Accel-type thfc_seed answers "Unknown Error" here
        # (confirmed live 2026-08-16), matching the manual's own
        # "FUNC_NAME에는 Force 또는 Moment 타입의 시간이력 함수만 사용 가능" warning.
        #
        # PUT /db/THNL used to kill the Gen NX session (confirmed twice live
        # 2026-08-16, v2.1 build 08/14/2026) -- MAPI-2468, root-caused and
        # patched by MIDASIT 2026-08-17 (a stale time-history-key delete in
        # the data layer left a dangling reference the API layer then
        # dereferenced after the transaction). Re-tested live 2026-08-25 on
        # Gen NX v2.1, build 08/20/2026: PUT succeeds in ~0.2s, session
        # stays healthy. Restriction to Civil-only lifted; both products
        # confirmed.
        Case(
            DynamicNodalLoad,
            {"ITEMS": [{"ID": 1, "THLCNAME": "THIS_SEED", "FUNC_NAME": "THFC_FORCE_SEED",
                        "DIR": "X", "ARRIVAL_TIME": 0, "SCALE_FACTOR": 1.0}]},
            {"ITEMS": [{"ID": 1, "THLCNAME": "THIS_SEED", "FUNC_NAME": "THFC_FORCE_SEED",
                        "DIR": "X", "ARRIVAL_TIME": 0, "SCALE_FACTOR": 1.5}]},
            lambda p: p["ITEMS"][0].get("SCALE_FACTOR"), 1.0, 1.5,
            item_id=1, needs=("this_seed", "thfc_force_seed"), confirmed=True,
        ),
        Case(
            TimeVaryingStaticLoad,
            {"THIS_LCNAME": "THIS_SEED", "SLOAD": "DL", "THIS_FUNCNAME": "THFC_SEED",
             "ATIME": 0, "SCALE": 1.0},
            {"THIS_LCNAME": "THIS_SEED", "SLOAD": "DL", "THIS_FUNCNAME": "THFC_SEED",
             "ATIME": 0, "SCALE": 1.5},
            lambda p: p.get("SCALE"), 1.0, 1.5,
            needs=("this_seed", "thfc_seed"), confirmed=True,
        ),
        # The original probe omitted the manual Request Example's optional
        # Y/Z functions and all three arrival-time fields.  Supply that
        # complete documented shape before treating a live failure as a
        # product finding.
        # db/dynamic_loads.py's own docstring already flags this endpoint
        # as "Keyed by node/group id" (unlike THNL's plain node id) --
        # possibly needs a real multi-support boundary/support group
        # defined first, not just any integer key. Not resolved as a
        # simple fixture problem; same class of finding as /db/NLLP,
        # /db/WVLD, /db/GRDP, /db/TDMF, /db/RPSC, /db/STRPSSM.
        Case(
            MultipleSupportExcitation,
            {"ITEMS": [{"ID": 1, "LCNAME": "THIS_SEED", "ANGLE": 0, "FUNCX": "THFC_SEED",
                        "SCALEX": 1.0, "ATIMEX": 0, "FUNCY": "THFC_SEED",
                        "SCALEY": 1.0, "ATIMEY": 0, "FUNCZ": "THFC_SEED",
                        "SCALEZ": 0.667, "ATIMEZ": 0}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "THIS_SEED", "ANGLE": 0, "FUNCX": "THFC_SEED",
                        "SCALEX": 1.5, "ATIMEX": 0, "FUNCY": "THFC_SEED",
                        "SCALEY": 1.0, "ATIMEY": 0, "FUNCZ": "THFC_SEED",
                        "SCALEZ": 0.667, "ATIMEZ": 0}]},
            lambda p: p["ITEMS"][0].get("SCALEX"), 1.0, 1.5,
            item_id=1, needs=("this_seed", "thfc_seed"), confirmed=True,
        ),
    ]


def _extras6_cases() -> List[Case]:
    """batch 6: the seismic-device family from db.boundary, deferred out of
    extras1 for its deeply nested COMMON payloads. Each is an independent
    definition table (not node-keyed), so item_id=1 is free in a document
    that hasn't touched these tables yet -- no seed step needed.

    Payloads are transcribed from the manual's own POST examples (05_DB_Boundary
    #16-20), not the leaner Specifications tables, per this project's
    standing preference for worked examples over tables when they disagree.
    In particular, SDVI's example sends all twelve ITEM fields and SDVE's
    sends fourteen fields the earlier table-only fixture omitted.

    SDHY and SDIS are Gen-only per db/boundary.py's own PRODUCTS (404 on
    Civil, confirmed 2026-07-29). /db/DRLS (#24, also Gen-only) stays
    deferred: its payload is `{<node id>: {}}`, an empty object with no
    field to distinguish a create from an update, so it doesn't fit this
    checker's create/update/probe shape.

    The pre-2026-08-25 fixtures omitted fields now present in the manual's
    Request Examples. Their historical "Wrong Field" observations are not
    evidence against these complete shapes; re-test the complete examples
    before drawing a server-behaviour conclusion.
    """

    def _sdvi_common(name: str) -> dict:
        return {"NAME": name, "DESC": "Seismic Oil Damper 500kN",
                "INPUT_METHOD": 0, "COMPANY": "SUMITOMO",
                "PRODUCT_NAME": "OD-500", "TYPE_NUMBER": "OD500-A"}

    def _sdvi_item(active: bool, *, ce: float = 0) -> dict:
        """All twelve manual Request-Example fields, for each of six DOFs."""
        return {
            "OPT_DOF": active, "CE": ce, "P1": 1000 if active else 0,
            "C1": 200 if active else 0, "ALPHA1": 0.5 if active else 1,
            "K0": 0, "EXFN_PY": 1, "EXFN_VY": 1, "EXFN_DE": 0.3,
            "EXFN_DC": 1, "OPT_EXFN_CE": False, "EXFN_CE": 1,
        }

    return [
        Case(
            SeismicDeviceViscousDamper,
            {"COMMON": _sdvi_common("SDVI_CRUD"), "DEVICE_TYPE": "",
             "DAMPER_TYPE": 2, "DASHPOT_TYPE": 2, "INPUT_TYPE": 0,
             "INPUT_TYPE_EXFN": 0,
             "ITEM": [
                 _sdvi_item(True, ce=500),
                 _sdvi_item(False), _sdvi_item(False), _sdvi_item(False),
                 _sdvi_item(False), _sdvi_item(False),
             ]},
            {"COMMON": _sdvi_common("SDVI_CRUD"), "DEVICE_TYPE": "",
             "DAMPER_TYPE": 2, "DASHPOT_TYPE": 2, "INPUT_TYPE": 0,
             "INPUT_TYPE_EXFN": 0,
             "ITEM": [
                 _sdvi_item(True, ce=800),
                 _sdvi_item(False), _sdvi_item(False), _sdvi_item(False),
                 _sdvi_item(False), _sdvi_item(False),
            ]},
            lambda p: p["ITEM"][0].get("CE"), 500, 800,
            confirmed=True,
        ),
        Case(
            SeismicDeviceViscoelasticDamper,
            {"COMMON": {"NAME": "SDVE_CRUD", "DESC": "", "INPUT_METHOD": 0,
                        "PRODUCT_NAME": "GR100-Series", "TYPE_NUMBER": "GR100-200"},
             "MATERIAL_TYPE": "GR100", "SHEAR_AREA": 0.05, "THICKNESS": 0.02,
             "MULTIPL": 1, "DIR": "Dx", "FREQ": 0, "STIFF_FACTOR": 1,
             "DAMP_FACTOR": 1, "REF_T": 20, "LIMIT_DEF": 0.3, "EFF_STIFF": 0,
             "EQUI_DAMP": 0, "OPT_MOUNT_STIFF": True, "MOUNT_STIFF": 1200,
             "OPT_KINETIC_FRIC": False, "KINETIC_FRIC": 0},
            {"COMMON": {"NAME": "SDVE_CRUD", "DESC": "", "INPUT_METHOD": 0,
                        "PRODUCT_NAME": "GR100-Series", "TYPE_NUMBER": "GR100-200"},
             "MATERIAL_TYPE": "GR100", "SHEAR_AREA": 0.08, "THICKNESS": 0.02,
             "MULTIPL": 1, "DIR": "Dx", "FREQ": 0, "STIFF_FACTOR": 1,
             "DAMP_FACTOR": 1, "REF_T": 20, "LIMIT_DEF": 0.3, "EFF_STIFF": 0,
            "EQUI_DAMP": 0, "OPT_MOUNT_STIFF": True, "MOUNT_STIFF": 1200,
            "OPT_KINETIC_FRIC": False, "KINETIC_FRIC": 0},
            lambda p: p.get("SHEAR_AREA"), 0.05, 0.08,
            confirmed=True,
        ),
        Case(
            SeismicDeviceSteelDamper,
            {"COMMON": {"NAME": "SDST_CRUD", "DESC": "", "INPUT_METHOD": 0,
                        "COMPANY": "", "PRODUCT_NAME": "SD-300",
                        "TYPE_NUMBER": "SD300-A"},
             "DIR": "Dx", "SDST_HYS_MODEL": "BL2", "K0": 1000,
             "P1": 100, "ALPHA1": 0.2, "KB": 2000, "BL2": {"BETA": 0}},
            {"COMMON": {"NAME": "SDST_CRUD", "DESC": "", "INPUT_METHOD": 0,
                        "COMPANY": "", "PRODUCT_NAME": "SD-300",
                        "TYPE_NUMBER": "SD300-A"},
             "DIR": "Dx", "SDST_HYS_MODEL": "BL2", "K0": 1000,
             "P1": 120, "ALPHA1": 0.2, "KB": 2000, "BL2": {"BETA": 0}},
            lambda p: p.get("P1"), 100, 120,
            confirmed=True,
        ),
        Case(
            SeismicDeviceHystereticIsolator,
            {"COMMON": {"NAME": "SDHY_CRUD", "DESC": "", "INPUT_METHOD": 0,
                        "COMPANY": "", "PRODUCT_NAME": "HI-500",
                        "TYPE_NUMBER": "HI500-A"},
             "SDHY_HYS_MODEL": "DegradingBiLinear", "MSS": 8, "K0": 5000,
             "P1": 100, "P2": 0, "ALPHA1": 1, "ALPHA2": 0, "BETA": 0.5,
             "Phi": 0, "LAMBDA": 8},
            {"COMMON": {"NAME": "SDHY_CRUD", "DESC": "", "INPUT_METHOD": 0,
                        "COMPANY": "", "PRODUCT_NAME": "HI-500",
                        "TYPE_NUMBER": "HI500-A"},
             "SDHY_HYS_MODEL": "DegradingBiLinear", "MSS": 8, "K0": 6000,
             "P1": 100, "P2": 0, "ALPHA1": 1, "ALPHA2": 0, "BETA": 0.5,
             "Phi": 0, "LAMBDA": 8},
            lambda p: p.get("K0"), 5000, 6000,
            products=("gen",), confirmed=True,
        ),
        Case(
            SeismicDeviceIsolator,
            # The manual's literal SLD worked example is a proven branch on
            # Gen.  The LRB branch below the same endpoint remains a separate
            # documented-but-unresolved product finding, so it must not make
            # this endpoint-level public CRUD fixture perpetually fail.
            {"COMMON": {"NAME": "SDIS_CRUD", "DESC": "", "INPUT_METHOD": 0,
                        "COMPANY": "", "PRODUCT_NAME": "", "TYPE_NUMBER": ""},
             "SDIS_DEV_TYPE": "SLD", "MSS": 8, "TAU_K": 1.0, "TAU_Q": 1.0,
             "KV": 150000,
             "SB": {"AS": 0.05, "K0": 100000, "QD": 2, "Pi_VALUE": 0,
                    "MU0": 0.05}},
            {"COMMON": {"NAME": "SDIS_CRUD", "DESC": "", "INPUT_METHOD": 0,
                        "COMPANY": "", "PRODUCT_NAME": "", "TYPE_NUMBER": ""},
             "SDIS_DEV_TYPE": "SLD", "MSS": 8, "TAU_K": 1.0, "TAU_Q": 1.0,
             "KV": 160000,
             "SB": {"AS": 0.05, "K0": 100000, "QD": 2, "Pi_VALUE": 0,
                    "MU0": 0.05}},
            lambda p: p.get("KV"), 150000, 160000,
            products=("gen",), confirmed=True,
        ),
    ]


def _extras7_seeds() -> List[SeedStep]:
    """batch 7: the standalone/frame-attachable remainder of db.static_loads.

    pnld_seed and fbld7_seed are separate records from their siblings'
    own CRUD cases (which delete themselves at the end of their round
    trip) purely so PNLA/FBLA have something stable to reference while
    those siblings run -- same pattern as extras5's spfc/thfc seeds.
    posp_seed/posl_seed exist for the same reason, feeding EPST/EPSE's
    SOIL_PROP/SEIS_LOAD name references.

    The base seed model (_seed_model) already has a PLATE element (id 4,
    nodes 5-8, a flat plate in the XY plane at Z=0) alongside the frame
    chain (elements 1-3), so PNLA (needs a real plate) and FMLD (keyed by
    element id) both have something real to attach to without this tier
    building any geometry of its own.

    pnld_seed/fbld7_seed both land at id 1, not the requested 90 -- same
    STLD/FBLD-family renumbering as extras1/extras5's seeds (confirmed
    live 2026-08-16), so the id-90 request is cosmetic; downstream cases
    reference id 1. posp_seed's ITEMS need to span from GROUND_LEVEL down
    to at least BEDROCK_LEVEL (5+5+15=25m matching the manual's own
    3-layer example) -- a single layer answered "Unknown Error" on POST,
    the same class of undocumented cross-field relationship as /db/SPAN's
    item-count-vs-list-length rule.

    posl_seed intentionally uses the manual's original field set
    (CODE/METHOD/EPA/SDS/SD1/USER_GROUP/IF/RMF): confirmed live 2026-08-16
    that /db/POSL's *live* schema is product-asymmetric -- Gen NX's
    GET/`.info()` schema matches the manual almost exactly (plus two
    undocumented fields, EPGAeff/Kae), while Civil NX's actual schema is a
    completely different, smaller field set (SRF/DAMP_RATIO instead of
    EPA/SDS/SD1/METHOD/USER_GROUP/RMF, and CODE rejected outright -- see
    the extras7_cases() POSL cases below). This seed only needs to work on
    Gen, since EPSE (the only thing that references it by name) is
    gen-only here.
    """
    return [
        SeedStep("pnld_seed", lambda c: PlaneLoadType.create(
            {90: {"NAME": "PNLD_SEED", "DESC": "", "LTYPE": "AREA",
                  "COPY_X": [0], "COPY_Y": [0],
                  "AREALOAD": {"bUNIFORM": True, "b3PNT": False,
                               "X": [0, 4, 4, 0], "Y": [0, 0, -4, -4],
                               "LOAD": [-5.0, -5.0, -5.0, -5.0]}}},
            client=c)),
        SeedStep("fbld7_seed", lambda c: FloorLoadType.create(
            {90: {"NAME": "FBLD_SEED", "DESC": "",
                  "ITEM": [{"LCNAME": "DL", "FLOOR_LOAD": 4.0,
                            "OPT_SUB_BEAM_WEIGHT": True}]}},
            client=c)),
        SeedStep("posp_seed", lambda c: SoilProperty.create(
            {90: {"NAME": "POSP_SEED", "DESC": "", "OPT_USE_N": False,
                  "GROUND_LEVEL": 0.0, "BEDROCK_LEVEL": -25.0,
                  "FOOTING_LEVEL": -10.0,
                  "ITEMS": [{"HEIGHT": 5.0, "ANGLE_OR_N": 28, "DENSITY": 17.0,
                             "VS": 150, "KH": 10000, "DISP": 0.001},
                            {"HEIGHT": 5.0, "ANGLE_OR_N": 32, "DENSITY": 18.0,
                             "VS": 200, "KH": 20000, "DISP": 0.001},
                            {"HEIGHT": 15.0, "ANGLE_OR_N": 35, "DENSITY": 19.0,
                             "VS": 300, "KH": 50000, "DISP": 0.001}]}},
            client=c)),
        SeedStep("posl_seed", lambda c: SeismicLoadParam.create(
            {90: {"NAME": "POSL_SEED", "CODE": "KDS(41-17-00:2019)",
                  "METHOD": "EQV_STATIC", "SZ": "1", "EPA": 0.22, "SC": "S2",
                  "FA": 1.0, "FV": 1.4, "SDS": 0.2933, "SD1": 0.1467,
                  "USER_GROUP": "1", "IF": 1.5, "RMF": 3.0}},
            client=c)),
    ]


def _extras7_cases() -> List[Case]:
    return [
        # id 1 is pnld_seed (see seed docstring); this case lands at id 2.
        # Full CRUD re-confirmed on Gen NX and Civil NX 2026-08-31.
        Case(
            PlaneLoadType,
            {"NAME": "PNLD_CRUD", "DESC": "", "LTYPE": "AREA",
             "COPY_X": [0], "COPY_Y": [0],
             "AREALOAD": {"bUNIFORM": True, "b3PNT": False,
                          "X": [0, 4, 4, 0], "Y": [0, 0, -4, -4],
                          "LOAD": [-5.0, -5.0, -5.0, -5.0]}},
            {"NAME": "PNLD_CRUD", "DESC": "", "LTYPE": "AREA",
             "COPY_X": [0], "COPY_Y": [0],
             "AREALOAD": {"bUNIFORM": True, "b3PNT": False,
                          "X": [0, 4, 4, 0], "Y": [0, 0, -4, -4],
                          "LOAD": [-8.0, -8.0, -8.0, -8.0]}},
            lambda p: p["AREALOAD"]["LOAD"][0], -5.0, -8.0,
            item_id=2, needs=("pnld_seed",), confirmed=True,
        ),
        # POINT_ORIGIN/AXIS_X/AXIS_Y trace the base model's own plate (element
        # 4, nodes 5-8: (0,-4,0),(4,-4,0),(4,-8,0),(0,-8,0)) so ON_PLANE
        # selection has something real to find. PNLD_KEY=1 is pnld_seed's
        # landed id, not the 90 it was requested at.
        #
        # LOAD_GROUP is dropped despite the manual/TypedDict marking it
        # Required -- confirmed live 2026-08-16 that sending *any*
        # non-empty LOAD_GROUP answers "Wrong Field" on Civil NX
        # (bisected: identical payload with the key omitted succeeds), so
        # it's either not actually required or must reference a
        # pre-existing Load Group this fixture doesn't define.
        Case(
            PlaneLoad,
            {"LCNAME": "LC_SCRATCH", "PNLD_KEY": 1, "ELEM_TYPE": "PLATE",
             "POINT_ORIGIN": [0, -4, 0], "AXIS_X": [4, -4, 0], "AXIS_Y": [4, -8, 0],
             "TOL": 0.001, "SELECT_TYPE": "ON_PLANE", "LOAD_DIR": "GLOBAL_Z",
             "PROJECT_TYPE": "NO"},
            {"LCNAME": "LC_SCRATCH", "PNLD_KEY": 1, "ELEM_TYPE": "PLATE",
             "POINT_ORIGIN": [0, -4, 0], "AXIS_X": [4, -4, 0], "AXIS_Y": [4, -8, 0],
             "TOL": 0.002, "SELECT_TYPE": "ON_PLANE", "LOAD_DIR": "GLOBAL_Z",
             "PROJECT_TYPE": "NO"},
            lambda p: p.get("TOL"), 0.001, 0.002,
            item_id=1, needs=("pnld_seed",), confirmed=True,
        ),
        # ⚠️ Confirmed failing live 2026-08-16 (Civil NX v2.2, build
        # 08/14/2026) with "Unknown Error" -- tried the base model's own
        # plate corners (5-8) and the unrelated frame-chain nodes (1-4),
        # both winding orders, FLOOR_DIST_TYPE 1 and 2, and the manual's
        # full optional-field set. None resolved it. Not a fixture problem
        # in any of the ways this project's other renumbering/reference
        # gotchas have been; same unresolved class as /db/NLLP, /db/WVLD,
        # /db/SDVI (batch 6), etc.
        Case(
            FloorLoad,
            {"FLOOR_LOAD_TYPE_NAME": "FBLD_SEED", "FLOOR_DIST_TYPE": 1,
             "DIR": "GZ", "NODES": [5, 6, 7, 8], "LOAD_ANGLE": 0},
            {"FLOOR_LOAD_TYPE_NAME": "FBLD_SEED", "FLOOR_DIST_TYPE": 1,
             "DIR": "GZ", "NODES": [5, 6, 7, 8], "LOAD_ANGLE": 15},
            lambda p: p.get("LOAD_ANGLE"), 0, 15,
            item_id=1, needs=("fbld7_seed",),
        ),
        # Keyed by element id -- element 1 is a base-model beam.
        Case(
            FinishingMaterialLoad,
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "",
                        "COVERING_TYPE": "ENVELOP",
                        "COVERING_RANGE": ["HALF", "HALF", "FULL", "FULL"],
                        "THICKNESS": 0.2, "DENSITY": 24.5, "DIR": "GZ",
                        "SCALE_FACTOR": 1.0}]},
            {"ITEMS": [{"ID": 1, "LCNAME": "LC_SCRATCH", "GROUP_NAME": "",
                        "COVERING_TYPE": "ENVELOP",
                        "COVERING_RANGE": ["HALF", "HALF", "FULL", "FULL"],
                        "THICKNESS": 0.2, "DENSITY": 24.5, "DIR": "GZ",
                        "SCALE_FACTOR": 1.5}]},
            lambda p: p["ITEMS"][0].get("SCALE_FACTOR"), 1.0, 1.5,
            item_id=1, confirmed=True,
        ),
        # 3 ITEMS spanning GROUND_LEVEL to BEDROCK_LEVEL, matching the
        # manual's own layer-depth relationship (see seed docstring).
        Case(
            SoilProperty,
            {"NAME": "POSP_CRUD", "DESC": "", "OPT_USE_N": False,
             "GROUND_LEVEL": 0.0, "BEDROCK_LEVEL": -25.0, "FOOTING_LEVEL": -10.0,
             "ITEMS": [{"HEIGHT": 5.0, "ANGLE_OR_N": 28, "DENSITY": 17.0,
                        "VS": 150, "KH": 10000, "DISP": 0.001},
                       {"HEIGHT": 5.0, "ANGLE_OR_N": 32, "DENSITY": 18.0,
                        "VS": 200, "KH": 20000, "DISP": 0.001},
                       {"HEIGHT": 15.0, "ANGLE_OR_N": 35, "DENSITY": 19.0,
                        "VS": 300, "KH": 50000, "DISP": 0.001}]},
            {"NAME": "POSP_CRUD", "DESC": "", "OPT_USE_N": False,
             "GROUND_LEVEL": 0.0, "BEDROCK_LEVEL": -25.0, "FOOTING_LEVEL": -10.0,
             "ITEMS": [{"HEIGHT": 5.0, "ANGLE_OR_N": 28, "DENSITY": 20.0,
                        "VS": 150, "KH": 10000, "DISP": 0.001},
                       {"HEIGHT": 5.0, "ANGLE_OR_N": 32, "DENSITY": 18.0,
                        "VS": 200, "KH": 20000, "DISP": 0.001},
                       {"HEIGHT": 15.0, "ANGLE_OR_N": 35, "DENSITY": 19.0,
                        "VS": 300, "KH": 50000, "DISP": 0.001}]},
            lambda p: p["ITEMS"][0].get("DENSITY"), 17.0, 20.0,
            item_id=91, products=("gen",), confirmed=True,
        ),
        # ⚠️ Confirmed failing live 2026-08-16 (Gen NX v2.1, build
        # 08/14/2026) with "Wrong Field" -- field names match /info's own
        # schema exactly, and bisected several variants (SEL_TYPE=GRUP,
        # EP_TYPE=ACTIVE, blank SOIL_PROP, no IN_PT, with
        # PRES_PROFILE_ITEMS) with no change. Not resolved as a fixture
        # problem; same unresolved class as /db/FBLA just above.
        Case(
            StaticEarthPressure,
            {"LOADCASE": "LC_SCRATCH", "DIR": "XY", "ANGLE": 0, "IN_PT": [0, 0, 0],
             "SF": 1.0, "EP_TYPE": "AT_REST", "SURCHARGE_LOAD": 10.0,
             "WATER_LEVEL": -5.0, "SOIL_PROP": "POSP_SEED", "SEL_TYPE": "ELEMENT",
             "ELEM_TYPE": "FRAME", "ELEM_LIST": [1, 2, 3]},
            {"LOADCASE": "LC_SCRATCH", "DIR": "XY", "ANGLE": 0, "IN_PT": [0, 0, 0],
             "SF": 1.5, "EP_TYPE": "AT_REST", "SURCHARGE_LOAD": 10.0,
             "WATER_LEVEL": -5.0, "SOIL_PROP": "POSP_SEED", "SEL_TYPE": "ELEMENT",
             "ELEM_TYPE": "FRAME", "ELEM_LIST": [1, 2, 3]},
            lambda p: p.get("SF"), 1.0, 1.5,
            item_id=1, needs=("posp_seed",), products=("gen",),
        ),
        # ⚠️ Product-asymmetric live schema, confirmed 2026-08-16 -- see the
        # seed docstring above. Split into two cases since a single
        # payload can't satisfy both products' actual field sets.
        Case(
            SeismicLoadParam,
            {"NAME": "POSL_CRUD", "SZ": "1", "SRF": 0.22, "SC": "S2",
             "FA": 1.0, "FV": 1.4, "DAMP_RATIO": 0.05},
            {"NAME": "POSL_CRUD", "SZ": "1", "SRF": 0.22, "SC": "S2",
             "FA": 1.0, "FV": 1.4, "DAMP_RATIO": 0.08},
            lambda p: p.get("DAMP_RATIO"), 0.05, 0.08,
            item_id=91, products=("civil",), confirmed=True,
        ),
        Case(
            SeismicLoadParam,
            {"NAME": "POSL_CRUD", "CODE": "KDS(41-17-00:2019)", "METHOD": "EQV_STATIC",
             "SZ": "1", "EPA": 0.22, "SC": "S2", "FA": 1.0, "FV": 1.4,
             "SDS": 0.2933, "SD1": 0.1467, "USER_GROUP": "1", "IF": 1.5, "RMF": 3.0},
            {"NAME": "POSL_CRUD", "CODE": "KDS(41-17-00:2019)", "METHOD": "EQV_STATIC",
             "SZ": "1", "EPA": 0.22, "SC": "S2", "FA": 1.0, "FV": 1.4,
             "SDS": 0.2933, "SD1": 0.1467, "USER_GROUP": "1", "IF": 1.5, "RMF": 3.5},
            lambda p: p.get("RMF"), 3.0, 3.5,
            item_id=92, products=("gen",), confirmed=True,
        ),
        # SOIL_PROP references posp_seed, which is Gen-only (POSP itself is
        # a GEN_ONLY endpoint) -- restricted to Gen here even though
        # EPSE's own PRODUCTS covers both, since there's no equivalent
        # Civil fixture to reference. Civil's own EPSE round trip is
        # untested by this case, not confirmed broken.
        #
        # ⚠️ Also confirmed failing live 2026-08-16 (Gen NX) with
        # "Wrong Field", same unresolved class as EPST just above --
        # untested whether it's the same underlying cause.
        Case(
            SeismicEarthPressure,
            {"LOADCASE": "LC_SCRATCH", "DIR": "XY", "ANGLE": 0, "IN_PT": [0, 0, 0],
             "SF": 1.0, "CODE": "KDS(41-17-00:2019)", "SEIS_LOAD": "POSL_SEED",
             "LAYER_PARAM": "SINGLE", "LAYER_LV": 0, "SOIL_PROP": "POSP_SEED",
             "SEL_TYPE": "ELEMENT", "ELEM_TYPE": "FRAME", "ELEM_LIST": [1, 2, 3]},
            {"LOADCASE": "LC_SCRATCH", "DIR": "XY", "ANGLE": 0, "IN_PT": [0, 0, 0],
             "SF": 1.5, "CODE": "KDS(41-17-00:2019)", "SEIS_LOAD": "POSL_SEED",
             "LAYER_PARAM": "SINGLE", "LAYER_LV": 0, "SOIL_PROP": "POSP_SEED",
             "SEL_TYPE": "ELEMENT", "ELEM_TYPE": "FRAME", "ELEM_LIST": [1, 2, 3]},
            lambda p: p.get("SF"), 1.0, 1.5,
            item_id=1, needs=("posp_seed", "posl_seed"), products=("gen",),
        ),
    ]


def _extras8_seeds() -> List[SeedStep]:
    """BCCT's vBOUNDARY.vBG entries must reference real /db/BNGR boundary
    groups -- confirmed live 2026-08-16: the manual's own example uses
    made-up names ("BG1"/"BG2") and answers "Boundary Group not found:
    BG1" verbatim. This seed creates them for real."""
    return [
        SeedStep("bngr_seed", lambda c: BoundaryGroup.create(
            {1: {"NAME": "BG1"}, 2: {"NAME": "BG2"}}, client=c)),
    ] + _lane_code_seed("AASHTO LRFD")


def _extras8_cases() -> List[Case]:
    """batch 8: the tractable subset of db.analysis_control -- 9 of its 21
    endpoints. All 9 are singleton "control data" tables (one record, id 1,
    no per-model geometry to reference beyond the base seed's own load
    cases "DL"/"LC_SCRATCH"). BCCT needs bngr_seed and MVCT needs the
    documented AASHTO LRFD moving-load-code selector. Deferred: the 5 Hyper-S
    (``-M1``) variants (Civil-only, deeply
    nested payloads) and the 4 country-specific MVCT variants (MVCTch/id/
    bs/tr -- large, code-specific field sets not worth the fixture cost
    yet).
    """
    return [
        # ⚠️ Confirmed failing live 2026-08-16 on both products, but with
        # different symptoms:
        # - Civil NX (v2.2, build 08/14/2026): TOL never persists as
        #   written. POST with TOL=0.001 succeeds and reads back
        #   correctly, but a follow-up PUT changing only TOL to 0.0005
        #   (and separately, to 0.01) reads back 0.001 both times --
        #   confirmed even after DELETE + a fresh POST with TOL=0.01,
        #   ruling out a PUT-specific bug. TOL appears fixed at 0.001
        #   server-side regardless of what's sent.
        # - Gen NX (v2.1, build 08/14/2026): every POST answers
        #   "Wrong Field" outright, including a bare {ITER, TOL}-only
        #   payload and one matching /info's own live schema exactly
        #   (which differs from Civil's and the manual's -- Gen has no
        #   CLATS field but does have an undocumented ACWC one; adding
        #   ACWC changes the error to "Wrong Key", suggesting it's
        #   read-only, not the cause either).
        # Neither resolved as a fixture problem.
        Case(
            MainControlData,
            {"ARDC": True, "ANRC": True, "ITER": 20, "TOL": 0.001,
             "CSECF": False, "TRS": True, "CRBAR": False, "BMSTRESS": False,
             "CLATS": False},
            {"ARDC": True, "ANRC": True, "ITER": 20, "TOL": 0.0005,
             "CSECF": False, "TRS": True, "CRBAR": False, "BMSTRESS": False,
             "CLATS": False},
            lambda p: p.get("TOL"), 0.001, 0.0005,
            item_id=1,
        ),
        Case(
            PDeltaAnalysisControl,
            {"ITER": 5, "TOL": 1e-05, "PDEL_CASES": [
                {"LCNAME": "DL", "FACTOR": 1.0}, {"LCNAME": "LC_SCRATCH", "FACTOR": 1.0}]},
            {"ITER": 8, "TOL": 1e-05, "PDEL_CASES": [
                {"LCNAME": "DL", "FACTOR": 1.0}, {"LCNAME": "LC_SCRATCH", "FACTOR": 1.0}]},
            lambda p: p.get("ITER"), 5, 8,
            item_id=1, confirmed=True,
        ),
        Case(
            BucklingAnalysisControl,
            {"MODE_NUM": 12, "OPT_POSITIVE": True, "OPT_CONSIDER_AXIAL_ONLY": True,
             "LOAD_FACTOR_FROM": 0, "LOAD_FACTOR_TO": 0, "OPT_STURM_SEQ": True,
             "ITEMS": [{"LCNAME": "DL", "FACTOR": 1, "LOAD_TYPE": 1},
                       {"LCNAME": "LC_SCRATCH", "FACTOR": 1, "LOAD_TYPE": 0}]},
            {"MODE_NUM": 6, "OPT_POSITIVE": True, "OPT_CONSIDER_AXIAL_ONLY": True,
             "LOAD_FACTOR_FROM": 0, "LOAD_FACTOR_TO": 0, "OPT_STURM_SEQ": True,
             "ITEMS": [{"LCNAME": "DL", "FACTOR": 1, "LOAD_TYPE": 1},
                       {"LCNAME": "LC_SCRATCH", "FACTOR": 1, "LOAD_TYPE": 0}]},
            lambda p: p.get("MODE_NUM"), 12, 6,
            item_id=1, confirmed=True,
        ),
        # ⚠️ TYPE="EIGEN" (Subspace Iteration, the manual's own first
        # worked example) answers "FREQ_RANGE is required for LANCZOS." --
        # confirmed live 2026-08-16 that "EIGEN" isn't accepted as a TYPE
        # value at all; the server evidently only recognises "LANCZOS" and
        # "RITZ" despite the manual and /info schema both listing EIGEN.
        # Switched to the manual's Lanczos example instead, which passed
        # on Gen NX on 2026-08-16.  Civil NX then returned the identical
        # FREQ_RANGE error, but Civil NX 2026 v2.2 build 08/26/2026 completed
        # this exact documented payload on 2026-08-31 without FREQ_RANGE.
        # Keep separate product cases so the fixture retains that evidence
        # rather than inferring a version-independent product rule.
        Case(
            EigenvalueAnalysisControl,
            {"TYPE": "LANCZOS", "iFREQ": 30, "bMINMAX": True, "FRMIN": 0.1,
             "FRMAX": 50, "bSTRUM": True},
            {"TYPE": "LANCZOS", "iFREQ": 50, "bMINMAX": True, "FRMIN": 0.1,
             "FRMAX": 50, "bSTRUM": True},
            lambda p: p.get("iFREQ"), 30, 50,
            item_id=1, products=("civil",), confirmed=True,
        ),
        Case(
            EigenvalueAnalysisControl,
            {"TYPE": "LANCZOS", "iFREQ": 30, "bMINMAX": True, "FRMIN": 0.1,
             "FRMAX": 50, "bSTRUM": True},
            {"TYPE": "LANCZOS", "iFREQ": 50, "bMINMAX": True, "FRMIN": 0.1,
             "FRMAX": 50, "bSTRUM": True},
            lambda p: p.get("iFREQ"), 30, 50,
            item_id=1, products=("gen",), confirmed=True,
        ),
        # ⚠️ Product-asymmetric, confirmed live 2026-08-16: this exact
        # payload passes clean on Gen NX (confirmed=True below) but fails
        # on Civil NX -- POSTs successfully (200/201, no error body) but a
        # GET immediately after reads THETA back as 0, not the 1 that was
        # sent, reproduced twice including after a DELETE + fresh POST.
        # Split into two cases since only one product's round trip
        # actually completes.
        Case(
            HeatOfHydrationAnalysisControl,
            {"FINAL_STAGE": True, "STAGE_NAME": "", "THETA": 1, "INIT_TEMP": 20,
             "EVAL": "GAUSS", "OPT_USE_EQUI_AGE": True, "OPT_INCL_SELF_WEIGHT": False,
             "SELF_WEIGHT_FACTOR": -1, "OPT_IS_CREEP_SHRINKAGE": True,
             "ITEM": {"TYPE": "BOTH", "CREEP_CALC_METHOD": 0,
                      "M_GENERAL": {"ITER": 20, "TOL": 0.001}}},
            {"FINAL_STAGE": True, "STAGE_NAME": "", "THETA": 0.5, "INIT_TEMP": 20,
             "EVAL": "GAUSS", "OPT_USE_EQUI_AGE": True, "OPT_INCL_SELF_WEIGHT": False,
             "SELF_WEIGHT_FACTOR": -1, "OPT_IS_CREEP_SHRINKAGE": True,
             "ITEM": {"TYPE": "BOTH", "CREEP_CALC_METHOD": 0,
                      "M_GENERAL": {"ITER": 20, "TOL": 0.001}}},
            lambda p: p.get("THETA"), 1, 0.5,
            item_id=1, products=("civil",),
        ),
        Case(
            HeatOfHydrationAnalysisControl,
            {"FINAL_STAGE": True, "STAGE_NAME": "", "THETA": 1, "INIT_TEMP": 20,
             "EVAL": "GAUSS", "OPT_USE_EQUI_AGE": True, "OPT_INCL_SELF_WEIGHT": False,
             "SELF_WEIGHT_FACTOR": -1, "OPT_IS_CREEP_SHRINKAGE": True,
             "ITEM": {"TYPE": "BOTH", "CREEP_CALC_METHOD": 0,
                      "M_GENERAL": {"ITER": 20, "TOL": 0.001}}},
            {"FINAL_STAGE": True, "STAGE_NAME": "", "THETA": 0.5, "INIT_TEMP": 20,
             "EVAL": "GAUSS", "OPT_USE_EQUI_AGE": True, "OPT_INCL_SELF_WEIGHT": False,
             "SELF_WEIGHT_FACTOR": -1, "OPT_IS_CREEP_SHRINKAGE": True,
             "ITEM": {"TYPE": "BOTH", "CREEP_CALC_METHOD": 0,
                      "M_GENERAL": {"ITER": 20, "TOL": 0.001}}},
            lambda p: p.get("THETA"), 1, 0.5,
            item_id=1, products=("gen",), confirmed=True,
        ),
        # The complete manual payload answered "Unknown Error" on an empty
        # document. A 2026-09-14 isolated rerun established the missing
        # prerequisite: selecting the manual's AASHTO LRFD code is sufficient.
        # No lane, vehicle, or moving-load case is needed for this control.
        Case(
            MovingLoadAnalysisControl,
            {"METHOD": "EXACT", "POINT": "INF", "iIGP": 0, "iIGPN": 3,
             "PLATE": "NODAL", "bSTRCALC": True, "bCONCURRENT": True,
             "bCONCLINK": True, "FRAME": "AXIAL", "bCSTRCALC": True,
             "bREAC": True, "bRG": False, "RGN": "",
             "bDISP": True, "bDG": False, "DGN": "",
             "bFM": True, "bFG": False, "FGN": "",
             "bL": True, "bLG": False, "LGN": ""},
            {"METHOD": "EXACT", "POINT": "INF", "iIGP": 0, "iIGPN": 5,
             "PLATE": "NODAL", "bSTRCALC": True, "bCONCURRENT": True,
             "bCONCLINK": True, "FRAME": "AXIAL", "bCSTRCALC": True,
             "bREAC": True, "bRG": False, "RGN": "",
             "bDISP": True, "bDG": False, "DGN": "",
             "bFM": True, "bFG": False, "FGN": "",
             "bL": True, "bLG": False, "LGN": ""},
            lambda p: p.get("iIGPN"), 3, 5,
            item_id=1, needs=("lane_code_AASHTO LRFD",), confirmed=True,
        ),
        Case(
            SettlementAnalysisControlData,
            {"CONCURRENT_CALC": True, "CONCURRENT_LINK": False},
            {"CONCURRENT_CALC": False, "CONCURRENT_LINK": False},
            lambda p: p.get("CONCURRENT_CALC"), True, False,
            item_id=1, confirmed=True,
        ),
        # ⚠️ Product-asymmetric, confirmed live 2026-08-16: this exact
        # payload passes clean on Gen NX (confirmed=True below) but fails
        # on Civil NX with "LINE_SEARCH_OPTION is required when
        # OPT_ENABLE_LINE_SEARCH is true." -- neither field appears in the
        # manual or in /info's own live schema at all. Tried explicitly
        # setting OPT_ENABLE_LINE_SEARCH=False (still the same error) and
        # adding a guessed LINE_SEARCH_OPTION="AUTO" alongside
        # OPT_ENABLE_LINE_SEARCH=True (also the same error, unchanged) --
        # neither cleared it on Civil. Split into two cases since only one
        # product's round trip actually completes.
        Case(
            NonlinearAnalysisControlData,
            {"NONLINEAR_TYPE": "GEOM+MATL", "ITERATION_METHOD": "NEWTON",
             "NUMBER_STEPS": 1, "MAX_ITERATIONS": 30,
             "OPT_ENERGY_NORM": True, "ENERGY_NORM": 0.001,
             "OPT_DISPLACEMENT_NORM": True, "DISPLACEMENT_NORM": 0.001,
             "OPT_FORCE_NORM": True, "FORCE_NORM": 0.001,
             "NEWTON_ITEMS": [{"ITERATION_METHOD": "NEWTON", "LCNAME": "LC_SCRATCH",
                               "NUMBER_STEPS": 1, "MAX_ITERATIONS": 30, "LOAD_FACTORS": [1]}]},
            {"NONLINEAR_TYPE": "GEOM+MATL", "ITERATION_METHOD": "NEWTON",
             "NUMBER_STEPS": 1, "MAX_ITERATIONS": 50,
             "OPT_ENERGY_NORM": True, "ENERGY_NORM": 0.001,
             "OPT_DISPLACEMENT_NORM": True, "DISPLACEMENT_NORM": 0.001,
             "OPT_FORCE_NORM": True, "FORCE_NORM": 0.001,
             "NEWTON_ITEMS": [{"ITERATION_METHOD": "NEWTON", "LCNAME": "LC_SCRATCH",
                               "NUMBER_STEPS": 1, "MAX_ITERATIONS": 50, "LOAD_FACTORS": [1]}]},
            lambda p: p.get("MAX_ITERATIONS"), 30, 50,
            item_id=1, products=("civil",),
        ),
        Case(
            NonlinearAnalysisControlData,
            {"NONLINEAR_TYPE": "GEOM+MATL", "ITERATION_METHOD": "NEWTON",
             "NUMBER_STEPS": 1, "MAX_ITERATIONS": 30,
             "OPT_ENERGY_NORM": True, "ENERGY_NORM": 0.001,
             "OPT_DISPLACEMENT_NORM": True, "DISPLACEMENT_NORM": 0.001,
             "OPT_FORCE_NORM": True, "FORCE_NORM": 0.001,
             "NEWTON_ITEMS": [{"ITERATION_METHOD": "NEWTON", "LCNAME": "LC_SCRATCH",
                               "NUMBER_STEPS": 1, "MAX_ITERATIONS": 30, "LOAD_FACTORS": [1]}]},
            {"NONLINEAR_TYPE": "GEOM+MATL", "ITERATION_METHOD": "NEWTON",
             "NUMBER_STEPS": 1, "MAX_ITERATIONS": 50,
             "OPT_ENERGY_NORM": True, "ENERGY_NORM": 0.001,
             "OPT_DISPLACEMENT_NORM": True, "DISPLACEMENT_NORM": 0.001,
             "OPT_FORCE_NORM": True, "FORCE_NORM": 0.001,
             "NEWTON_ITEMS": [{"ITERATION_METHOD": "NEWTON", "LCNAME": "LC_SCRATCH",
                               "NUMBER_STEPS": 1, "MAX_ITERATIONS": 50, "LOAD_FACTORS": [1]}]},
            lambda p: p.get("MAX_ITERATIONS"), 30, 50,
            item_id=1, products=("gen",), confirmed=True,
        ),
        # vBOUNDARY.vBG entries must reference real /db/BNGR boundary
        # groups (bngr_seed above) -- the manual's own "BG1"/"BG2" example
        # values are made-up and answer "Boundary Group not found: BG1".
        # It passed on Gen NX on 2026-08-16.  Civil NX then returned the
        # identical error even with bngr_seed's real groups in place, but
        # Civil NX 2026 v2.2 build 08/26/2026 completed the same fixture on
        # 2026-08-31.  Keep separate product cases as build-specific evidence.
        Case(
            BoundaryChangeAssignment,
            {"bSPT": True, "bSPR": True, "bGSPR": False, "bCGLINK": False,
             "bSSSF": True, "bPSSF": False, "bRLS": True, "bCDOF": False,
             "vBOUNDARY": [{"BGCNAME": "BGL1", "vBG": ["BG1", "BG2"]}],
             "vLOADANAL": [{"TYPE": "ST", "BGCNAME": "BGL1", "LCNAME": "LC_SCRATCH"}]},
            {"bSPT": False, "bSPR": True, "bGSPR": False, "bCGLINK": False,
             "bSSSF": True, "bPSSF": False, "bRLS": True, "bCDOF": False,
             "vBOUNDARY": [{"BGCNAME": "BGL1", "vBG": ["BG1", "BG2"]}],
             "vLOADANAL": [{"TYPE": "ST", "BGCNAME": "BGL1", "LCNAME": "LC_SCRATCH"}]},
            lambda p: p.get("bSPT"), True, False,
            item_id=1, needs=("bngr_seed",), products=("civil",), confirmed=True,
        ),
        Case(
            BoundaryChangeAssignment,
            {"bSPT": True, "bSPR": True, "bGSPR": False, "bCGLINK": False,
             "bSSSF": True, "bPSSF": False, "bRLS": True, "bCDOF": False,
             "vBOUNDARY": [{"BGCNAME": "BGL1", "vBG": ["BG1", "BG2"]}],
             "vLOADANAL": [{"TYPE": "ST", "BGCNAME": "BGL1", "LCNAME": "LC_SCRATCH"}]},
            {"bSPT": False, "bSPR": True, "bGSPR": False, "bCGLINK": False,
             "bSSSF": True, "bPSSF": False, "bRLS": True, "bCDOF": False,
             "vBOUNDARY": [{"BGCNAME": "BGL1", "vBG": ["BG1", "BG2"]}],
             "vLOADANAL": [{"TYPE": "ST", "BGCNAME": "BGL1", "LCNAME": "LC_SCRATCH"}]},
            lambda p: p.get("bSPT"), True, False,
            item_id=1, needs=("bngr_seed",), products=("gen",), confirmed=True,
        ),
    ]


def _extras9_seeds() -> List[SeedStep]:
    """batch 9: db.node_element's Domain feature (MADO/SBDO/DOEL).

    ⚠️ /db/MADO itself is a genuine unresolved finding, confirmed live
    2026-08-16 on both products: POST answers `{"message": ""}` -- no
    error body, HTTP success -- but the record never actually appears in
    a follow-up GET. Reproduced with several payload variants including
    the manual's own literal request-body example (NAME="DM1", TYPE=4,
    MATL=0, PROP=0, SUB_TYPE=2) verbatim, and with MATL/PROP pointed at
    the base seed model's real material/section ids (1/1) instead of the
    manual's placeholder 0/0. Every attempt is silently a no-op. This
    seed is kept (rather than deleted) so SBDO/DOEL's own cases still run
    and demonstrate the downstream effect -- they reference a domain name
    that was never actually created, which is the real reason they fail
    too, not necessarily a defect of their own.
    """
    return [
        SeedStep("mado_seed", lambda c: MainDomain.create(
            {90: {"NAME": "DM1_SEED", "TYPE": 4, "MATL": 1, "PROP": 1, "SUB_TYPE": 1},
             91: {"NAME": "DM2_SEED", "TYPE": 4, "MATL": 1, "PROP": 1, "SUB_TYPE": 1}},
            client=c)),
    ]


def _extras9_cases() -> List[Case]:
    """None of these 3 have ever passed live -- see the seed docstring
    above for /db/MADO's root cause. SBDO and DOEL are included anyway
    (not skipped) since a future MADO fix might unblock them without any
    change needed here."""
    return [
        Case(
            MainDomain,
            {"NAME": "DM_CRUD", "TYPE": 4, "MATL": 1, "PROP": 1, "SUB_TYPE": 1},
            {"NAME": "DM_CRUD", "TYPE": 4, "MATL": 1, "PROP": 1, "SUB_TYPE": 2},
            lambda p: p.get("SUB_TYPE"), 1, 2,
            item_id=92, needs=("mado_seed",),
        ),
        # DOMAIN_NAME references mado_seed's DM1_SEED by name -- which was
        # never actually created (see above), so this fails downstream of
        # /db/MADO's own defect, not necessarily one of its own. Civil-only
        # field set (MEMB_TYPE_CIVIL/REBAR_AXIS_TYPE/STR_UCS/AXIS_VECTOR),
        # per the manual's own Civil worked example.
        Case(
            SubDomain,
            {"SUB_DOMAIN_NAME": "SDM_CRUD", "V1": 0, "V2": 90, "DOMAIN_NAME": "DM1_SEED",
             "MEMB_TYPE_CIVIL": 1, "REBAR_AXIS_TYPE": 0, "STR_UCS": "",
             "AXIS_VECTOR": [0, 0, 0, 0, 0, 0]},
            {"SUB_DOMAIN_NAME": "SDM_CRUD", "V1": 0, "V2": 45, "DOMAIN_NAME": "DM1_SEED",
             "MEMB_TYPE_CIVIL": 1, "REBAR_AXIS_TYPE": 0, "STR_UCS": "",
             "AXIS_VECTOR": [0, 0, 0, 0, 0, 0]},
            lambda p: p.get("V2"), 90, 45,
            item_id=1, needs=("mado_seed",), products=("civil",),
        ),
        # Gen-only field set (MEMBER_TYPE/bUseMt/THICKNESS/rebar layout),
        # per the manual's own Gen worked example. Same downstream-of-MADO
        # caveat as the Civil case above.
        Case(
            SubDomain,
            {"SUB_DOMAIN_NAME": "SDM_CRUD", "V1": 0, "V2": 90, "DOMAIN_NAME": "DM1_SEED",
             "MEMBER_TYPE": 1, "bUseMt": True, "THICKNESS": 0.2,
             "OPT_BASIC_REBAR": True, "TOP_REBAR_NAME_X": "D13", "TOP_REBAR_SPACE_X": 0.15,
             "BOTTOM_REBAR_NAME_X": "D13", "BOTTOM_REBAR_SPACE_X": 0.15,
             "TOP_REBAR_NAME_Y": "D13", "TOP_REBAR_SPACE_Y": 0.15,
             "BOTTOM_REBAR_NAME_Y": "D13", "BOTTOM_REBAR_SPACE_Y": 0.15,
             "OPT_REBAR_MATL": False, "REBAR_MATL_KEY": 0},
            {"SUB_DOMAIN_NAME": "SDM_CRUD", "V1": 0, "V2": 45, "DOMAIN_NAME": "DM1_SEED",
             "MEMBER_TYPE": 1, "bUseMt": True, "THICKNESS": 0.2,
             "OPT_BASIC_REBAR": True, "TOP_REBAR_NAME_X": "D13", "TOP_REBAR_SPACE_X": 0.15,
             "BOTTOM_REBAR_NAME_X": "D13", "BOTTOM_REBAR_SPACE_X": 0.15,
             "TOP_REBAR_NAME_Y": "D13", "TOP_REBAR_SPACE_Y": 0.15,
             "BOTTOM_REBAR_NAME_Y": "D13", "BOTTOM_REBAR_SPACE_Y": 0.15,
             "OPT_REBAR_MATL": False, "REBAR_MATL_KEY": 0},
            lambda p: p.get("V2"), 90, 45,
            item_id=1, needs=("mado_seed",), products=("gen",),
        ),
        # Keyed by element id -- element 4 is the base model's plate.
        # KEY_DOMAIN/MAIN_DOMAIN_NAME reference mado_seed's domains, which
        # were never actually created (same downstream caveat as SBDO
        # above).
        Case(
            DomainElement,
            {"TYPE": 0, "KEY_DOMAIN": 90, "MAIN_DOMAIN_NAME": "DM1_SEED"},
            {"TYPE": 0, "KEY_DOMAIN": 91, "MAIN_DOMAIN_NAME": "DM2_SEED"},
            lambda p: p.get("MAIN_DOMAIN_NAME"), "DM1_SEED", "DM2_SEED",
            item_id=4, needs=("mado_seed",),
        ),
    ]


def _extras10_seeds() -> List[SeedStep]:
    """batch 10: the standalone (non-construction-stage-keyed) subset of
    db.construction_stage's heat-of-hydration family. Deferred: /db/HECB,
    /db/HSPT (both keyed by a construction-stage id, per the manual's own
    "Assign의 키(ID)는 시공단계 번호입니다" note) and /db/CSCS (references a
    stage name via ASTAGE) -- all three would need a real construction
    stage built first, which this tier doesn't do.

    hsfc_seed creates two named functions (not one) so /db/HAHS's update
    step can switch FUNC_NAME to a second real function rather than a
    no-op -- same two-seed pattern as the boundary tier's spring_types.
    Named with a "10" suffix (SG10_SEED/BG10_SEED) to avoid colliding
    with the "stage" tier's own SG_SEED/BG_SEED when a full run exercises
    both tiers against the same document.
    """
    def _groups10(c: MidasClient) -> None:
        StructureGroup.create({90: {"NAME": "SG10_SEED"}}, client=c)
        BoundaryGroup.create({90: {"NAME": "BG10_SEED"}}, client=c)

    return [
        SeedStep("groups10", _groups10),
        SeedStep("hsfc_seed", lambda c: HeatSourceFunction.create(
            {90: {"NAME": "HSFC_SEED", "TYPE": "CONST", "TEMP_CONST": 10},
             91: {"NAME": "HSFC_SEED_2", "TYPE": "CONST", "TEMP_CONST": 15}},
            client=c)),
        SeedStep("solid10_seed", lambda c: _seed_hexahedral_solid(
            c, node_start=30, element_id=50)),
    ]


def _extras10_cases() -> List[Case]:
    return [
        Case(
            AmbientTemperatureFunction,
            {"NAME": "ETFC_CRUD", "TYPE": "CONST", "TEMP": 30},
            {"NAME": "ETFC_CRUD", "TYPE": "CONST", "TEMP": 15},
            lambda p: p.get("TEMP"), 30, 15,
            item_id=1, confirmed=True,
        ),
        Case(
            ConvectionCoefficientFunction,
            {"NAME": "CCFC_CRUD", "TYPE": "CONST", "COEF": 15},
            {"NAME": "CCFC_CRUD", "TYPE": "CONST", "COEF": 20},
            lambda p: p.get("COEF"), 15, 20,
            item_id=1, confirmed=True,
        ),
        # id 92: hsfc_seed's two records land at 90/91.
        Case(
            HeatSourceFunction,
            {"NAME": "HSFC_CRUD", "TYPE": "CONST", "TEMP_CONST": 10},
            {"NAME": "HSFC_CRUD", "TYPE": "CONST", "TEMP_CONST": 25},
            lambda p: p.get("TEMP_CONST"), 10, 25,
            item_id=92, needs=("hsfc_seed",), confirmed=True,
        ),
        # Keyed by element id. A minimal, documented 8-node hexahedral SOLID
        # at element 50 is the real target; a beam and a plate were both
        # correctly rejected in the first attempt. Confirmed full CRUD on
        # Gen NX v2.1 and Civil NX v2.2, build 08/26/2026.
        Case(
            AssignHeatSource,
            {"FUNC_NAME": "HSFC_SEED"},
            {"FUNC_NAME": "HSFC_SEED_2"},
            lambda p: p.get("FUNC_NAME"), "HSFC_SEED", "HSFC_SEED_2",
            item_id=50, needs=("hsfc_seed", "solid10_seed"), confirmed=True,
        ),
        # ⚠️ Confirmed failing live 2026-08-16 (Civil NX v2.2, build
        # 08/14/2026) with "Wrong Key" -- a different error class than
        # this session's usual "Wrong Field"/"Unknown Error". Bisected to
        # ITEMS specifically: every other field succeeds individually
        # (each answers the normal "Wrong Field" for an incomplete
        # payload), but adding ITEMS -- with real frame node ids, real
        # plate node ids, or a single node -- always flips the error to
        # "Wrong Key" instead. Live /info's own schema says ITEMS is a
        # plain integer array, matching what was sent, so the mismatch
        # isn't a documented one. Also tried the undocumented
        # START_STAGE/END_STAGE string fields /info reveals (absent from
        # the manual entirely) both empty and omitted -- no change.
        Case(
            PipeCooling,
            {"NAME": "HPCE_CRUD", "DIAMETER": 0.025, "COEF": 850, "HEAT": 4200,
             "DENSITY": 1000, "TEMPER": 15, "FLOW_RATE": 20, "START_TIME": 0,
             "END_TIME": 168, "ITEMS": [1, 2, 3, 4]},
            {"NAME": "HPCE_CRUD", "DIAMETER": 0.025, "COEF": 850, "HEAT": 4200,
             "DENSITY": 1000, "TEMPER": 20, "FLOW_RATE": 20, "START_TIME": 0,
             "END_TIME": 168, "ITEMS": [1, 2, 3, 4]},
            lambda p: p.get("TEMPER"), 15, 20,
            item_id=1,
        ),
        # NODE1/NODE2 are the base model's own frame nodes; LCNAME is the
        # base model's own "LC_SCRATCH" load case.
        Case(
            SetBackLoad,
            {"NODE1": 1, "NODE2": 2, "DX": 0, "DY": 0.005, "DZ": 0,
             "LCNAME": "LC_SCRATCH", "GROUP_NAME": ""},
            {"NODE1": 1, "NODE2": 2, "DX": 0, "DY": 0.01, "DZ": 0,
             "LCNAME": "LC_SCRATCH", "GROUP_NAME": ""},
            lambda p: p.get("DY"), 0.005, 0.01,
            item_id=1, confirmed=True,
        ),
        # ACT_ELEM/ACT_BNGR reference groups10's real structure/boundary
        # groups by name -- the manual's own worked example uses made-up
        # group names, so this fixture uses real ones from the start
        # rather than repeating the /db/BCCT lesson from batch 8.
        Case(
            ConstructionStageForHydration,
            {"NAME": "HSTG_CRUD", "bINITAL_TEMP": True, "INITIAL_TEMP": 20,
             "ADD_STEP": [1, 3, 7, 14, 28], "ACT_ELEM": ["SG10_SEED"],
             "ACT_BNGR": ["BG10_SEED"], "DACT_BNGR": [], "ACT_LOAD": [],
             "DACT_LOAD": []},
            {"NAME": "HSTG_CRUD", "bINITAL_TEMP": True, "INITIAL_TEMP": 25,
             "ADD_STEP": [1, 3, 7, 14, 28], "ACT_ELEM": ["SG10_SEED"],
             "ACT_BNGR": ["BG10_SEED"], "DACT_BNGR": [], "ACT_LOAD": [],
             "DACT_LOAD": []},
            lambda p: p.get("INITIAL_TEMP"), 20, 25,
            item_id=1, needs=("groups10",), confirmed=True,
        ),
    ]


def _extras11_seeds() -> List[SeedStep]:
    """HECB/HSPT need their own stage, real names, and a real SOLID element.

    This tier is runnable alone, so it builds its own first construction
    stage and replaces the otherwise-frame element 1 only inside its
    throwaway model.
    """
    def _hecb_seed(c: MidasClient) -> None:
        BoundaryGroup.create({11: {"NAME": "BG11_SEED"}}, client=c)
        StructureGroup.create(
            {11: {"NAME": "SG11_SEED", "P_TYPE": 0, "E_LIST": [1]}},
            client=c,
        )
        ConvectionCoefficientFunction.create(
            {11: {"NAME": "CC11_SEED", "TYPE": "CONST", "COEF": 15}}, client=c)
        AmbientTemperatureFunction.create(
            {11: {"NAME": "AT11_SEED", "TYPE": "CONST", "TEMP": 20}}, client=c)

    def _stage11_seed(c: MidasClient) -> None:
        # A full run has already created the shared stage-1 record. A direct
        # extras11 run has not, so create the same documented minimum only
        # when it is absent. This keeps the tier independently runnable
        # without making a complete run fail on a duplicate seed.
        stages = ConstructionStage.get(client=c).get("STAG", {})
        if "1" in stages:
            return
        ConstructionStage.create(
            {1: {"NAME": "CS_SEED", "DURATION": 5, "bSV_RSLT": True,
                 "bSV_STEP": False, "bLOAD_STEP": False, "ADD_STEP": [],
                 "ACT_ELEM": [{"GRUP_NAME": "SG11_SEED", "AGE": 0}],
                 "ACT_BNGR": [{"BNGR_NAME": "BG11_SEED", "POS": "DEFORMED"}],
                 "ACT_LOAD": []}},
            client=c,
        )

    return [
        SeedStep("solid11_seed", lambda c: _seed_hexahedral_solid(
            c, node_start=40, element_id=1, replace_existing=True)),
        SeedStep("hecb_seed", _hecb_seed),
        SeedStep("stage11_seed", _stage11_seed),
    ]


def _extras11_cases() -> List[Case]:
    """batch 11a: /db/STCT, the one untested endpoint left in the
    tractable subset of db.analysis_control (the rest of the 12 still
    missing -- ACTL-M1/EIGV-M1/HHCT-M1/NLCT-M1/STCT-M1/BCGD-M1/BCGA-M1 are
    Hyper-S/-M1, MVCTch/id/bs/tr are large country-specific field sets --
    stay deferred per the extras8 docstring). Needs a real construction
    stage name, created by this tier as ``CS_SEED``.

    The manual's own worked example uses a made-up stage name ("CS1"),
    same class of mistake as /db/BCCT's "BG1"/"BG2" -- swapped for the
    real "CS_SEED" from the start. bINC_PDL (Civil NX only per its own
    TypedDict comment) is left out of this first attempt to keep one
    payload triable on both products; split into product variants if it
    turns out to matter.

    ⚠️ Confirmed failing live 2026-08-17 on both products, two different
    symptoms:
    - Civil NX: once a real construction stage is registered (stage_1
      above), /db/STCT already holds an auto-populated default record at
      id 1 -- POST answers "Key Already Exist" outright, and DELETE
      separately answers "[Error] Construction Stage Analysis Control
      Data cannot be deleted when the Construction Stage is registered."
      A manual PUT (bypassing this Case's POST-first flow) does succeed
      and echoes iITER/TOL correctly in its own response, but a follow-up
      GET drops both fields entirely -- confirmed on a second PUT with a
      different iITER value too, ruling out a one-off.
    - Gen NX: no pre-existing default record, so POST itself succeeds,
      but the same iITER/TOL silent-drop reproduces on the very first GET
      after create ("wrote 30, read back None").
    Every other field in this payload (FINAL_STAGE, CPFC, bCONV/bTRUSS/
    bBEAM, bCAMBER, bCHANGE_CABLE, iNLA_TYPE, bINC_TDE, bCNS, TYPE,
    iITER_CR, TOL_CR) persists correctly on both products -- only the two
    Linear-analysis-specific fields (iITER, TOL) are silently dropped. A
    2026-09-01 re-test used their actual documented branch, Linear plus
    Independent (iINC_NLA=0, iNLA_TYPE=0), and reproduced the same loss on
    both current products. The fixture therefore models that branch directly
    instead of hiding the defect behind an invalid branch combination.
    """
    return [
        Case(
            ConstructionStageAnalysisControlData,
            {"bLAST_FINAL": False, "FINAL_STAGE": "CS_SEED",
             "iINC_NLA": 0, "iNLA_TYPE": 0,
             "iITER": 30, "TOL": 0.01,
             "CPFC": "EXTERNAL",
             "bCONV": True, "bTRUSS": True, "bBEAM": True,
             "bCHANGE_CABLE": True, "bCAMBER": True},
            {"bLAST_FINAL": False, "FINAL_STAGE": "CS_SEED",
             "iINC_NLA": 0, "iNLA_TYPE": 0,
             "iITER": 50, "TOL": 0.01,
             "CPFC": "EXTERNAL",
             "bCONV": True, "bTRUSS": True, "bBEAM": True,
             "bCHANGE_CABLE": True, "bCAMBER": True},
            lambda p: p.get("iITER"), 30, 50,
            # The stage activates hecb_seed's groups by name.
            item_id=1, needs=("hecb_seed", "stage11_seed"),
        ),
        # batch 11c: HECB/HSPT are keyed by construction-stage number as the
        # manual says. item_id=1 is this tier's real ``CS_SEED``.
        # The manual's own worked examples use made-up group/function names
        # ("BG_SURF", "CC_Standard", "AT_Summer") -- swapped for hecb_seed's
        # real ones from the start, same lesson as /db/BCCT.
        #
        # ITEMS[].ID remains the manual's serial number 1. The isolated model
        # makes its first element a SOLID and activates it through a real
        # structure group in a real construction stage. This resolves the
        # earlier frame-element rejection without redefining the manual field
        # as an element id; confirmed full CRUD on both products, build
        # 08/26/2026.
        Case(
            ElementConvectionBoundary,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "BG11_SEED", "FACE_NO": 1,
                        "CCFC_NAME": "CC11_SEED", "ETFC_NAME": "AT11_SEED"}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "BG11_SEED", "FACE_NO": 2,
                        "CCFC_NAME": "CC11_SEED", "ETFC_NAME": "AT11_SEED"}]},
            lambda p: p["ITEMS"][0].get("FACE_NO"), 1, 2,
            # Listed in build order: the emitted npm setup follows ``needs``,
            # and the stage activates the group that names the solid.
            item_id=1, needs=("solid11_seed", "hecb_seed", "stage11_seed"),
            confirmed=True,
        ),
        Case(
            PrescribedTemperature,
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "BG11_SEED", "TEMPER": 15.0}]},
            {"ITEMS": [{"ID": 1, "GROUP_NAME": "BG11_SEED", "TEMPER": 20.0}]},
            lambda p: p["ITEMS"][0].get("TEMPER"), 15.0, 20.0,
            item_id=1, needs=("hecb_seed", "stage11_seed"), confirmed=True,
        ),
    ]


def _extras12_seeds() -> List[SeedStep]:
    """batch 12: db.bridge (GSBG/GCMB/CAMB/ULFC). All 4 Civil-only per
    db/bridge.py's own docstring except ULFC, which answers on Gen too.

    A single real /db/GRUP structure group, key 12, backs GCMB's
    GRUP_NAME, CAMB's three group-name fields, and GSBG's numeric
    BODY_ELEM_GRUP_K -- the manual's own worked examples use made-up
    names ("FSM"/"PSC-BN"/"Key-SegK1~K5" for CAMB, "CS_0".."CS_18" for
    GCMB), same lesson as /db/BCCT.
    """
    return [
        SeedStep("bridge_group", lambda c: StructureGroup.create(
            {12: {"NAME": "SG12_SEED"}, 13: {"NAME": "SG12_SEED_2"}}, client=c)),
    ]


def _extras12_cases() -> List[Case]:
    civil = ("civil",)
    return [
        Case(
            GeneralCamberControl,
            {"bSTART_PT_ZERO": True,
             "GCMB_BASE_ITEMS": [{"GRUP_NAME": "SG12_SEED", "DIRECTION": "+DX"}]},
            {"bSTART_PT_ZERO": True,
             "GCMB_BASE_ITEMS": [{"GRUP_NAME": "SG12_SEED", "DIRECTION": "-DX"}]},
            lambda p: p["GCMB_BASE_ITEMS"][0].get("DIRECTION"), "+DX", "-DX",
            item_id=1, needs=("bridge_group",), products=civil, confirmed=True,
        ),
        Case(
            FcmCamberControl,
            {"BODY_GROUP_NAME": "SG12_SEED", "SUPP_GROUP_NAME": "SG12_SEED",
             "KEYSEG_GROUP_NAME": "SG12_SEED"},
            {"BODY_GROUP_NAME": "SG12_SEED_2", "SUPP_GROUP_NAME": "SG12_SEED",
             "KEYSEG_GROUP_NAME": "SG12_SEED"},
            lambda p: p.get("BODY_GROUP_NAME"), "SG12_SEED", "SG12_SEED_2",
            item_id=1, needs=("bridge_group",), products=civil, confirmed=True,
        ),
        Case(
            BridgeGirderDiagram,
            {"NAME": "GSBG_CRUD", "BATCH": True, "BODY_ELEM_GRUP_K": 12,
             "ALLSTAGE": False, "DGRM_TYPE": 1, "MOMENT_COMP": 4, "SCALEFACTOR": 1},
            {"NAME": "GSBG_CRUD", "BATCH": True, "BODY_ELEM_GRUP_K": 12,
             "ALLSTAGE": False, "DGRM_TYPE": 1, "MOMENT_COMP": 2, "SCALEFACTOR": 1},
            lambda p: p.get("MOMENT_COMP"), 4, 2,
            item_id=1, needs=("bridge_group",), products=civil, confirmed=True,
        ),
        # TYPE="REAC" keyed by a real base-model node id (node 1).
        # ⚠️ POINT is only documented as meaningful for TYPE="BEAM", but
        # confirmed live 2026-08-17 it's actually required unconditionally
        # -- omitting it on a TYPE="REAC" payload answers "Wrong Field";
        # POINT=0 clears it.
        Case(
            UnknownLoadFactorConstraint,
            {"NAME": "ULFC_CRUD", "TYPE": "REAC", "OBJ_ID": 1, "POINT": 0, "COMP": 2,
             "EQ": True, "bVALUE": True, "VALUE": 500, "OtherObject": 0},
            {"NAME": "ULFC_CRUD", "TYPE": "REAC", "OBJ_ID": 1, "POINT": 0, "COMP": 2,
             "EQ": True, "bVALUE": True, "VALUE": 300, "OtherObject": 0},
            lambda p: p.get("VALUE"), 500, 300,
            item_id=1, confirmed=True,
        ),
    ]


def _extras13_cases() -> List[Case]:
    """batch 13: the tractable, non-rebar subset of db.design (8 of 13) --
    design-code selection, unbraced length, member/frame/slenderness
    definitions, and mark overrides. All are simple singleton or
    element-keyed tables, no analysis run needed.

    On 2026-09-01, seven cases round-tripped on both current builds. DSTL
    remains unconfirmed: its documented fixture completes on Civil but Gen
    returns a Steel Design Control Data error. Keep that product difference
    explicit rather than marking the shared case confirmed.

    Deferred: /db/RCHK
    (Civil-only, large nested vMAIN/vSUB_BAR/vLAYER rebar-check structures)
    and /db/REBB/REBC/REBW/REBR (Gen-only, similarly large rebar-data
    overrides -- REBW's own manual section was already found wrong and
    fixed against a live production model, see db/design.py; the other
    three untested here).

    DGNCODE values for DCON/DSTL: live-bisected 2026-08-24, not taken
    verbatim from the manual. The manual's own worked-example values
    ("ACI318-19"/"ACI318M-19"/"ACI318-14"/"ACI318M-14" for DCON, and
    "AISC(16th)-LRFD22" for DSTL) all answer "Wrong Field"/"[Error] Errors
    detected in Steel Design Control Data." on this Civil NX 2026 v2.2
    license -- reproduced on both POST and PUT, with and without a STEEL
    material present in the model, so it isn't a fixture/model-state gap.
    "KDS 24 14 21 : 2021" (DCON) and every other tested non-Eurocode/ASD89
    DSTL code (KDS/KBC/CSA/GB/BS/AS/IS/DIN/SIA/NBR/JGJ/AIJ families) fail
    the same way. Reads as a license/module gate on specific
    country-code editions, not a request-shape bug -- use values confirmed
    to actually round-trip on this license instead.
    """
    return [
        Case(
            RcDesignCode,
            {"DGNCODE": "KCI-USD12"},
            {"DGNCODE": "KCI-USD07"},
            lambda p: p.get("DGNCODE"), "KCI-USD12", "KCI-USD07",
            item_id=1, confirmed=True,
        ),
        Case(
            SteelDesignCode,
            {"DGNCODE": "Eurocode3-2:05"},
            {"DGNCODE": "AISC-ASD89"},
            lambda p: p.get("DGNCODE"), "Eurocode3-2:05", "AISC-ASD89",
            item_id=1,
        ),
        # Keyed by a real base-model BEAM element id (2).  The shared npm
        # fixture provisions that element before the element-keyed CRUD case.
        Case(
            UnbracedLength,
            {"LY": 9.464111, "LZ": 4, "LB": 4, "bNOTUSE": False,
             "bAUTOCALC": False, "LT": 9.464111},
            {"LY": 9.464111, "LZ": 4, "LB": 4, "bNOTUSE": False,
             "bAUTOCALC": False, "LT": 5.0},
            lambda p: p.get("LT"), 9.464111, 5.0,
            item_id=2, confirmed=True,
            setup=(
                {"seed": "ltsr_material"},
                {"seed": "ltsr_section"},
                {"seed": "ltsr_nodes"},
                {"seed": "ltsr_beam"},
            ),
        ),
        # AELEM must be elements of the same auto-detected member type
        # (COLUMN vs BEAM, from orientation) -- live-confirmed 2026-08-24:
        # [1, 2, 3] fails "Not Same Member Type" because element 1 (node
        # 1->2) is vertical (COLUMN) while 2/3 (node 2->3->4) are
        # horizontal (BEAM). Elements 2-3 alone share BEAM and group fine.
        Case(
            DesignMemberAssignment,
            {"AELEM": [2, 3], "bREVERSE": False},
            {"AELEM": [2, 3], "bREVERSE": True},
            lambda p: p.get("bREVERSE"), False, True,
            item_id=1, confirmed=True,
            setup=(
                {"seed": "ltsr_material"},
                {"seed": "ltsr_section"},
                {"seed": "ltsr_nodes"},
                {"seed": "ltsr_beam"},
                {"seed": "member_node"},
                {"seed": "member_beam"},
            ),
        ),
        Case(
            FrameDefinition,
            {"FRAMEX": "Braced Non-sway", "FRAMEY": "Braced Non-sway",
             "bAUTOKF": False, "DT": "XY"},
            {"FRAMEX": "Braced Non-sway", "FRAMEY": "Unbraced Sway",
             "bAUTOKF": True, "DT": "3D"},
            lambda p: p.get("DT"), "XY", "3D",
            item_id=1, confirmed=True,
        ),
        # Keyed by a real base-model BEAM element id (2), not the design-member
        # record id (1).  Both products returned "Not Found Key" for id 1 and
        # completed the full CRUD cycle for id 2 on 2026-08-31.
        Case(
            LimitingSlendernessRatio,
            {"bNOTCHECK": False, "COMP": 150, "TENS": 400},
            {"bNOTCHECK": False, "COMP": 200, "TENS": 300},
            lambda p: p.get("COMP"), 150, 200,
            item_id=2, confirmed=True,
            setup=(
                {"seed": "ltsr_material"},
                {"seed": "ltsr_section"},
                {"seed": "ltsr_nodes"},
                {"seed": "ltsr_beam"},
            ),
        ),
        # Keyed by a real base-model BEAM element id (2).  The shared npm
        # fixture provisions that element before the element-keyed CRUD case.
        Case(
            ModifyMemberType,
            {"TYPE": "COLUMN"},
            {"TYPE": "BEAM"},
            lambda p: p.get("TYPE"), "COLUMN", "BEAM",
            item_id=2, confirmed=True,
            setup=(
                {"seed": "ltsr_material"},
                {"seed": "ltsr_section"},
                {"seed": "ltsr_nodes"},
                {"seed": "ltsr_beam"},
            ),
        ),
        # WID_LIST is model-keyed. The explicit PLATE prerequisite was
        # verified through the npm public API on both products.
        Case(
            ModifyWallMark,
            {"MARKNAME": "W1", "WID_LIST": [4]},
            {"MARKNAME": "W1_RENAMED", "WID_LIST": [4]},
            lambda p: p.get("MARKNAME"), "W1", "W1_RENAMED",
            item_id=1, confirmed=True,
            setup=(
                {"seed": "ltsr_material"},
                {"seed": "wmak_thickness"},
                {"seed": "wmak_nodes"},
                {"seed": "wmak_plate"},
            ),
        ),
    ]


class _MvcdSwitch(MovingLoadCode):
    """PUT-only view of /db/MVCD, used to switch the singleton record's
    CODE mid-tier without re-POSTing over the record extras14's own
    mvcd_ksce_seed already created (which would answer "Key Already
    Exist") or DELETEing it afterward (which would undo the switch before
    DYFG/DYNF run)."""

    METHODS = frozenset({"GET", "PUT"})


def _extras14_seeds() -> List[SeedStep]:
    """batch 14: the 12 Civil-only-by-design endpoints (5 db.moving_loads,
    7 db.analysis_control Hyper-S/-M1 variants) -- Hyper-S is a Civil NX
    solver, so these were never reachable on Gen at all, unlike most of
    this project's Civil-only findings which are just unimplemented-on-
    Gen quirks of an otherwise-shared endpoint.

    CRGR/CJFG/DYLA reference a real /db/GRUP structure group by name (id
    14 to avoid colliding with any other tier's group ids); BCGD-M1
    references a real /db/BNGR boundary group; BCGA-M1 references both a
    real static load case name (this tier's own "DL14_SEED") and the
    BCGD-M1 record this tier creates. DYNF is keyed by a real element id,
    not a serial number -- reuses core's element 1.

    /db/MVCD is a shared singleton with mutually exclusive requirements:
    DYLA only accepts KSCE-LSD15/AASHTO LRFD/PENDOT, DYFG/DYNF only accept
    Eurocode. Seeds all run before any case (this harness doesn't
    interleave them), so satisfying both means seeding KSCE-LSD15 up
    front for DYLA and then switching to Eurocode via a plain MVCD
    update() *as a case*, positioned between DYLA and DYFG/DYNF in the
    list below.
    """
    return [
        SeedStep("sg14_seed", lambda c: StructureGroup.create(
            {14: {"NAME": "SG14_SEED"}}, client=c)),
        SeedStep("bngr14_seed", lambda c: BoundaryGroup.create(
            {14: {"NAME": "BG14_SEED"}}, client=c)),
        SeedStep("dl14_seed", lambda c: StaticLoadCase.create(
            {14: {"NAME": "DL14_SEED", "TYPE": "D", "DESC": ""}}, client=c)),
        SeedStep("mvcd_ksce_seed", lambda c: MovingLoadCode.create(
            {1: {"CODE": "KSCE-LSD15"}}, client=c)),
        SeedStep("bcgd_m1_seed", lambda c: DefineBoundaryCombinationHyperS.create(
            {1: {"BCG_NAME": "BCGD14_SEED", "GROUP_LIST": ["BG14_SEED"]}}, client=c)),
    ]


def _extras14_cases() -> List[Case]:
    civil = ("civil",)
    return [
        Case(
            ConcurrentReactionGroup,
            {"GROUPS": ["SG14_SEED"]}, {"GROUPS": ["SG14_SEED"]},
            lambda p: p.get("GROUPS"), ["SG14_SEED"], ["SG14_SEED"],
            item_id=1, needs=("sg14_seed",), products=civil, confirmed=True,
        ),
        Case(
            ConcurrentJointForceGroup,
            {"GROUPS": ["SG14_SEED"]}, {"GROUPS": ["SG14_SEED"]},
            lambda p: p.get("GROUPS"), ["SG14_SEED"], ["SG14_SEED"],
            item_id=1, needs=("sg14_seed",), products=civil, confirmed=True,
        ),
        # DYLA needs MVCD.CODE in {KSCE-LSD15, AASHTO LRFD, PENDOT} -- live-
        # confirmed 2026-08-25 ("[Error] Additional Dynamic Load Allowance
        # can be applied when Moving Load Code is entered as ..."), so this
        # runs against the tier's KSCE-LSD15 seed before the case below
        # switches the same singleton /db/MVCD record to Eurocode for
        # DYFG/DYNF. Seeds and cases don't interleave in this harness (all
        # seeds run before any case), so the code switch has to be its own
        # mid-list case, not a second seed.
        Case(
            DynamicLoadAllowance,
            {"FACTOR": 10.0, "ITEMS": ["SG14_SEED"]},
            {"FACTOR": 20.0, "ITEMS": ["SG14_SEED"]},
            lambda p: p.get("FACTOR"), 10.0, 20.0,
            item_id=1, needs=("sg14_seed", "mvcd_ksce_seed"), products=civil, confirmed=True,
        ),
        # Switches /db/MVCD from KSCE-LSD15 (DYLA, above) to EUROCODE
        # (DYFG/DYNF, below) via PUT only -- see the DYLA case's comment.
        # mvcd_ksce_seed already POSTed id 1, so this must not POST again
        # ("Key Already Exist"); _MvcdSwitch restricts METHODS to skip the
        # harness's create/read_back steps and go straight to PUT.
        Case(
            _MvcdSwitch,
            {"CODE": "KSCE-LSD15"}, {"CODE": "EUROCODE"},
            lambda p: p.get("CODE"), "KSCE-LSD15", "EUROCODE",
            item_id=1, needs=("mvcd_ksce_seed",), products=civil, confirmed=True,
        ),
        # ⚠️ Needs ALL 6 fields sent every time, live-confirmed 2026-08-25 --
        # the manual's own conditional requiredness (LENGTH/MAINTAIN_TYPE
        # only for INPUT_TYPE=0, HEIGHT_COVER only for OPT_REDUCE_EFF=true,
        # DYN_FACTOR only for INPUT_TYPE=1) answers "Wrong Field" on both
        # POST and PUT if any field is omitted -- see RailwayDynamicFactor
        # Payload's docstring in db/moving_loads.py. DYNF (below) does NOT
        # share this quirk.
        Case(
            RailwayDynamicFactor,
            {"INPUT_TYPE": 1, "LENGTH": 0, "MAINTAIN_TYPE": 0,
             "OPT_REDUCE_EFF": False, "HEIGHT_COVER": 0, "DYN_FACTOR": 1.2},
            {"INPUT_TYPE": 1, "LENGTH": 0, "MAINTAIN_TYPE": 0,
             "OPT_REDUCE_EFF": False, "HEIGHT_COVER": 0, "DYN_FACTOR": 1.5},
            lambda p: p.get("DYN_FACTOR"), 1.2, 1.5,
            item_id=1, needs=("mvcd_ksce_seed",), products=civil, confirmed=True,
            # Python reaches EUROCODE through the /db/MVCD case above.
            setup=({"seed": "mvcd_eurocode"},), setup_replaces=("mvcd_ksce_seed",),
        ),
        # Keyed by a real element id (core's element 1), not a serial number.
        Case(
            RailwayDynamicFactorByElement,
            {"INPUT_TYPE": 1, "DYN_FACTOR": 1.2},
            {"INPUT_TYPE": 1, "DYN_FACTOR": 1.5},
            lambda p: p.get("DYN_FACTOR"), 1.2, 1.5,
            item_id=1, needs=("mvcd_ksce_seed",), products=civil, confirmed=True,
            # Python reaches EUROCODE through the /db/MVCD case above.
            setup=({"seed": "mvcd_eurocode"},), setup_replaces=("mvcd_ksce_seed",),
        ),
        Case(
            MainControlDataHyperS,
            {"ARCD": True}, {"ARCD": False},
            lambda p: p.get("ARCD"), True, False,
            item_id=1, products=civil, confirmed=True,
        ),
        # FREQ_RANGE sent explicitly (OPT_USE=False) even though it's
        # documented optional -- EIGV (non-Hyper-S)'s Civil failure was an
        # undocumented-but-required FREQ_RANGE, so this variant sends it
        # up front rather than risking the same gap.
        Case(
            EigenvalueAnalysisControlHyperS,
            {"ANAL_TYPE": "LANCZOS", "FREQ_NO": 5, "FREQ_RANGE": {"OPT_USE": False}},
            {"ANAL_TYPE": "LANCZOS", "FREQ_NO": 10, "FREQ_RANGE": {"OPT_USE": False}},
            lambda p: p.get("FREQ_NO"), 5, 10,
            item_id=1, products=civil, confirmed=True,
        ),
        Case(
            HeatOfHydrationAnalysisControlHyperS,
            {"FINAL_STAGE": True, "OPT_IS_CREEP_SHRINKAGE": False},
            {"FINAL_STAGE": True, "OPT_IS_CREEP_SHRINKAGE": False, "INIT_TEMP": 25.0},
            lambda p: p.get("INIT_TEMP"), None, 25.0,
            item_id=1, products=civil, confirmed=True,
        ),
        # LC_SCOPE wants "ALL" (a scope keyword), not a load case name --
        # the manual's own worked example uses "ALL", live-confirmed this
        # is required (a real load case name here answers "Wrong Field").
        # CONV_CRITERIA needs at least one sub-object with OPT_USE=true and
        # a VALUE; all-false answers "Wrong Field" too.
        Case(
            NonlinearAnalysisControlHyperS,
            {"LC_SCOPE": "ALL", "NONLINEAR_TYPE": "GEOM", "ITER_METHOD": "FORCE",
             "LOAD_STEPS": {"STEP_MODE": "AUTO", "NUMBER_STEPS": 10, "OUTPUT": "EVERY"},
             "CONV_CRITERIA": {"DISP": {"OPT_USE": True, "VALUE": 0.001}}},
            {"LC_SCOPE": "ALL", "NONLINEAR_TYPE": "GEOM", "ITER_METHOD": "FORCE",
             "LOAD_STEPS": {"STEP_MODE": "AUTO", "NUMBER_STEPS": 20, "OUTPUT": "EVERY"},
             "CONV_CRITERIA": {"DISP": {"OPT_USE": True, "VALUE": 0.001}}},
            lambda p: p["LOAD_STEPS"].get("NUMBER_STEPS"), 10, 20,
            item_id=1, products=civil, confirmed=True,
        ),
        Case(
            ConstructionStageAnalysisControlDataHyperS,
            {"bLAST_FINAL": True, "ANAL_TYPE": {"iINC_NLA": 0, "iNLA_TYPE": 0}},
            {"bLAST_FINAL": True, "ANAL_TYPE": {"iINC_NLA": 1, "iNLA_TYPE": 0}},
            lambda p: p["ANAL_TYPE"].get("iINC_NLA"), 0, 1,
            item_id=1, products=civil, confirmed=True,
        ),
        Case(
            DefineBoundaryCombinationHyperS,
            {"BCG_NAME": "BCGD14_CRUD", "GROUP_LIST": ["BG14_SEED"]},
            {"BCG_NAME": "BCGD14_CRUD", "GROUP_LIST": ["BG14_SEED"]},
            lambda p: p.get("BCG_NAME"), "BCGD14_CRUD", "BCGD14_CRUD",
            item_id=2, needs=("bngr14_seed",), products=civil, confirmed=True,
        ),
        # ⚠️ BC_SELECT: the manual's own enum table is entirely wrong --
        # every value in it ("SECF"/"CONS"/"MCON"/...) answers "Wrong
        # Field" live. Real values come from GET /info/db/BCGA-M1 -- see
        # AssignBoundaryCombinationHyperSPayload's docstring in
        # db/analysis_control.py for the full corrected list.
        # BC_SELECT comes back in a server-chosen order, not the order sent
        # (live-confirmed 2026-08-25: sent ["SP","LC","EL"], read back
        # ["SP","EL","LC"]) -- probe sorts before comparing.
        Case(
            AssignBoundaryCombinationHyperS,
            {"BC_ASSIGN": [{"ANAL_TYPE": "ST", "LCNAME": "DL14_SEED", "BGCNAME": "BCGD14_SEED"}],
             "BC_SELECT": ["SP", "LC"]},
            {"BC_ASSIGN": [{"ANAL_TYPE": "ST", "LCNAME": "DL14_SEED", "BGCNAME": "BCGD14_SEED"}],
             "BC_SELECT": ["SP", "LC", "EL"]},
            lambda p: sorted(p.get("BC_SELECT", [])), ["LC", "SP"], ["EL", "LC", "SP"],
            item_id=1, needs=("bngr14_seed", "dl14_seed", "bcgd_m1_seed"),
            products=civil, confirmed=True, unordered=True,
        ),
    ]


def _extras15_seeds() -> List[SeedStep]:
    """Load cases used by the manual's prestress examples.

    /db/STLD is a known renumbering table, so the cases refer to these records
    by NAME and the emitted fixture marks the seed accordingly.
    """
    return [
        SeedStep(
            "prestress_load_cases",
            lambda client: StaticLoadCase.create(
                {
                    15: {"NAME": "PS15_SEED", "TYPE": "PS", "DESC": "prestress fixture"},
                    16: {"NAME": "PS16_SEED", "TYPE": "PS", "DESC": "prestress fixture"},
                },
                client=client,
            ),
        ),
    ]


def _polc_acceleration_payload(*, steps: int, product: str) -> Dict[str, Any]:
    """Return the manual's complete uniform-acceleration POLC branch.

    Five stopping-condition members are tagged Gen-only in the contract. The
    manual's shared example includes them, so remove them only for the Civil
    fixture instead of sending a known other-product field.
    """
    payload: Dict[str, Any] = {
        "LCNAME": "PUSH_ACC_X",
        "DESC": "",
        "INCRE_STEP": steps,
        "bCONS_PDELTA": False,
        "bUSEINITIAL": False,
        "bREACOUTPUT": False,
        "INCRE_METHOD": "LOAD",
        "STEPCTRLOPTION": "EQUAL",
        "INCFUNC_KEY": 0,
        "STIFF_RATIO": 0,
        "bLIMITDEFORMANGLE": True,
        "LIMITDEFORMANGLE": 10,
        "bDRIFTMAX": True,
        "bDRIFTCENTER": False,
        "bDRIFTAVER": False,
        "DISPCTRLOPTION": "GLOBAL",
        "GLOBAL_MAX_DISP": 0,
        "MASTERNODE": 0,
        "MASTERDIRECTION": "",
        "MASTERMAXDISP": 0,
        "LOADPATTERNTYPE": "ACC",
        "LOADPATTERN": [{"DIR": "DX", "SF": 1}],
    }
    if product == "civil":
        for key in (
            "bLIMITDEFORMANGLE",
            "LIMITDEFORMANGLE",
            "bDRIFTMAX",
            "bDRIFTCENTER",
            "bDRIFTAVER",
        ):
            del payload[key]
    return payload


def _iehc_payload(product: str, *, beam_loc: int = 1) -> Dict[str, Any]:
    """Return the manual request, excluding its explicitly Gen-only rows."""
    payload: Dict[str, Any] = {
        "BEAM_LOC": beam_loc,
        "BeamDivNumNy": 15,
        "BeamDivNumNz": 20,
        "WallConsOut": False,
        "WallDivNumZ": 8,
        "WallDivNumY": 1,
        "dR": 0.4,
        # The table says Integer, but the same manual request says "AUTO" and
        # recorded Gen /info independently types this one member as string.
        "WAreaSize": "AUTO",
        "OPT_ConsiderRebarArea1D": False,
        "OPT_ConsiderRebarAreaWall": False,
        "FAreaSizeCore": 1,
        "FAreaSizeCover": 1,
        "WAreaSizeCover": 1,
        "BeamDivNumNyCover": 20,
        "BeamDivNumNzCover": 15,
        "WallDivNumZCover": 8,
        "WallDivNumYCover": 1,
    }
    if product == "civil":
        gen_only = {
            "WallConsOut", "WallDivNumZ", "WallDivNumY", "dR", "WAreaSize",
            "OPT_ConsiderRebarAreaWall", "WAreaSizeCover", "WallDivNumZCover",
            "WallDivNumYCover",
        }
        payload = {key: value for key, value in payload.items() if key not in gen_only}
    return payload


def _polc_hypers_acceleration_payload(*, nltype: str = "PDELTA") -> Dict[str, Any]:
    """Build the dependency-free ACC/LOAD branch stated by the M1 contract."""
    return {
        "LCNAME": "PUSH_LOAD_X",
        "DESC": "Pushover load control case in X direction",
        "INCRE_STEP": 20,
        "NLTYPE": nltype,
        "bUSEINITIAL": False,
        "INCRE_METHOD": "LOAD",
        "CTRL_OPT": {"STEPCTRLOPTION": "EQUAL", "STIFF_RATIO": 80},
        "LOADPATTERNTYPE": "ACC",
        "LOADPATTERN": [{"DIR": "DX", "SF": 1}],
    }


def _extras15_cases() -> List[Case]:
    """Batch 15: tractable pushover and prestress assignments.

    The vendored manual identifies /db/IEPI's Assign key as an element id and
    documents B_IGNORE as the only record member. The base model owns element
    id 1. The same beam can carry /db/PRST; its load-case dependency is the
    replayable STLD seed above. /db/EXLD exercises that seed's two names using
    the exact array shape in the manual.
    """
    return [
        Case(
            IgnoreElementsForPushoverInitialLoad,
            {"B_IGNORE": False},
            {"B_IGNORE": True},
            lambda payload: payload.get("B_IGNORE"),
            False,
            True,
            item_id=1,
            confirmed=True,
        ),
        Case(
            ExternalLoadCaseForPretension,
            {"LCNAME_ITEM": ["PS15_SEED"]},
            {"LCNAME_ITEM": ["PS15_SEED", "PS16_SEED"]},
            lambda payload: payload.get("LCNAME_ITEM"),
            ["PS15_SEED"],
            ["PS15_SEED", "PS16_SEED"],
            item_id=1,
            needs=("prestress_load_cases",),
            confirmed=True,
        ),
        Case(
            PrestressBeamLoad,
            {
                "ITEMS": [{
                    "ID": 1,
                    "LCNAME": "PS15_SEED",
                    "GROUP_NAME": "",
                    "DIR": 1,
                    "TENSION": 1360,
                    "DISTANCE_I": 0.2,
                    "DISTANCE_M": 0.3,
                    "DISTANCE_J": 0.4,
                }],
            },
            {
                "ITEMS": [{
                    "ID": 1,
                    "LCNAME": "PS15_SEED",
                    "GROUP_NAME": "",
                    "DIR": 1,
                    "TENSION": 1500,
                    "DISTANCE_I": 0.2,
                    "DISTANCE_M": 0.3,
                    "DISTANCE_J": 0.4,
                }],
            },
            lambda payload: payload["ITEMS"][0].get("TENSION"),
            1360,
            1500,
            item_id=1,
            needs=("prestress_load_cases",),
            confirmed=True,
        ),
        # Uniform acceleration needs neither a prior analysis result nor an
        # extra static-load reference. Split products because the contract's
        # /info evidence marks five stopping-condition fields Gen-only.
        *[
            Case(
                PushoverLoadCase,
                _polc_acceleration_payload(steps=10, product=product),
                _polc_acceleration_payload(steps=12, product=product),
                lambda payload: payload.get("INCRE_STEP"),
                10,
                12,
                item_id=1,
                products=(product,),
                confirmed=True,
            )
            for product in ("gen", "civil")
        ],
        # MATD is GET/PUT-only and id 1 is the base model's concrete material.
        # The manual's EN04(RC)/ClassB example is refused by both products as
        # an unknown grade. A 2026-09-12 GET of the throwaway C24 material on
        # each product returned KS01(RC)/C24 with blank rebar code and grades;
        # replay that observed combination using the manual's PUT-only shape.
        Case(
            MaterialModifyConcrete,
            {},
            {
                "TYPE": "CONC",
                "NAME": "C24",
                "DATA1": {
                    "CODENAME": "KS01(RC)",
                    "CODEMATLNAME": "C24",
                },
                "REBAR_CODENAME": "",
                "MAINREBAR_REBARNAME": "",
                "SUBREBAR_REBARNAME": "",
                "MAINREBAR_B_FY": 500000,
                "SUBREBAR_B_FY": 600000,
            },
            lambda payload: payload.get("MAINREBAR_B_FY"),
            None,
            500000,
            item_id=1,
            confirmed=True,
        ),
        *[
            Case(
                InelasticHingeControl,
                _iehc_payload(product),
                _iehc_payload(product, beam_loc=2),
                lambda payload: payload.get("BEAM_LOC"),
                1,
                2,
                item_id=1,
                products=(product,),
                confirmed=True,
            )
            for product in ("gen", "civil")
        ],
        Case(
            PushoverLoadCaseHyperS,
            _polc_hypers_acceleration_payload(),
            _polc_hypers_acceleration_payload(nltype="NONE"),
            lambda payload: payload.get("NLTYPE"),
            "PDELTA",
            "NONE",
            item_id=1,
            products=("civil",),
            confirmed=True,
        ),
    ]


def _plastic_material_payload(name: str) -> Dict[str, Any]:
    """Return the manual's `/db/EPMT` Von-Mises Request Body record."""
    return {
        "NAME": name,
        "MODEL_TYPE": "VM",
        "VMISES": {
            "INIT_YIELD_STRESS": 235000,
            "OPT_HARDENING": 0,
            "HARDENING_TYPE": "ISO",
            "HARDENING_COEF": 21000,
        },
    }


def _inelastic_kent_park_payload(name: str, strength: float) -> Dict[str, Any]:
    """Return section 28's complete `/db/FIMP` Kent & Park example."""
    return {
        "NAME": name,
        "MATL_TYPE": "CONC",
        "HYS_MODEL": "KPM",
        "CONC": {
            "KENPAR": {
                "FC": strength,
                "PARTIAL_FACT": 1.0,
                "K": 1.0,
                "EC0": 0.002,
                "EC1_METHOD": 1,
                "EC1": 0.0035,
                "Z": 100,
                "ECU": 0.003,
                "STRENGTH_AFTER": 0,
            },
        },
    }


def _extras16_cases() -> List[Case]:
    """Task A properties whose complete values are stated by the manual."""
    args = (
        PlasticMaterial,
        _plastic_material_payload("Steel_VonMises"),
        _plastic_material_payload("Steel_VM"),
        lambda p: p.get("NAME"), "Steel_VonMises", "Steel_VM",
    )
    # The identical manual payload passes Gen but Civil refuses it with
    # "Wrong Field" even though both products expose the same /info schema.
    # Keep separate cases so Gen's evidence does not bless Civil's behaviour.
    return [
        Case(*args, item_id=1, products=("gen",), confirmed=True),
        Case(*args, item_id=1, products=("civil",)),
        Case(
            InelasticMaterialProperty,
            _inelastic_kent_park_payload("Conc_Kent&Park", 30000),
            _inelastic_kent_park_payload("Concrete_KP", 24000),
            lambda p: p.get("CONC", {}).get("KENPAR", {}).get("FC"),
            30000, 24000, item_id=3,
        ),
    ]


def _extras17_cases() -> List[Case]:
    """Task A pushover cases using ch14's documented wire values only.

    PHGE's two manual examples attach the same named hinge to elements 1 and
    2, which the shared base model supplies.  POGD's complete request example
    contains product-specific PHOP_OPT members, so this fixture intentionally
    keeps only the documented common required control fields.  POGD-M1 is
    PUT-only and the ch14 schema requires its GEO_NONL_TYPE, INIT_LOAD_TYPE,
    and ITER_CTRL group; choose the documented no-initial-load branch rather
    than fabricate load-case prerequisites.
    """
    phge_created = {
        "ID": 1,
        "TYPE": "BEAM",
        "HINGE_TYPE": "Myz_15",
        "FIBER_KEY": 0,
    }
    phge_updated = {**phge_created, "ID": 2}

    pogd_created = {
        "GEOMNONLINEAR_TYPE": "NONE",
        "INITLOADMETHOD": "PERFORM_ANAL",
        "INITLOAD": [],
        "bCONSIGNOREELEM": True,
        "NONL_OPT": {
            "bPERMITFAIL": True,
            "SUBSTEP": 10,
            "MAXITER": 10,
            "bDISPLNORM": True,
            "bFORCENORM": False,
            "bENERGYNORM": False,
            "DISPLNORM": 0.001,
            "FORCENORM": 0.001,
            "ENERGYNORM": 0.001,
            "bSHEARYIELDSTOP": False,
            "BSHEARYIELDSTOPBEAM": True,
            "bAXIALYIELDSTOP": False,
            "bAXIALYIELDSTOPBEAM": True,
            "bAXIALYIELDSTOPTRUSS": False,
            "bSUPPORTDZDIRSTOP": False,
            "bSUPPORTSTOPUPLIFTING": False,
            "bSUPPORTSTOPCOLLAPSE": False,
        },
        "NODECONNECTIVITY": "PINNED",
        "bSHOWGRAPHAFTER": True,
        "bSHOWGRAPGHDURING": False,
    }
    pogd_updated = copy.deepcopy(pogd_created)
    pogd_updated["NONL_OPT"]["MAXITER"] = 11

    pogd_m1_created = {
        "GEO_NONL_TYPE": 0,
        "INIT_LOAD_TYPE": 0,
        "ITER_CTRL": {
            "MAX_ITER": 30,
            "NORM_CTRL": {
                "DISP": {"OPT_USE": True, "VALUE": 0.001},
                "FORCE": {"OPT_USE": False},
                "ENERGY": {"OPT_USE": False},
            },
            "STIFF_UPD_SCHEME": 0,
            "ITER_BEF_UPDATE": 5,
        },
    }
    pogd_m1_updated = copy.deepcopy(pogd_m1_created)
    pogd_m1_updated["ITER_CTRL"]["MAX_ITER"] = 31

    # 2026-09-19, Build 09/15/2026, both SDKs: POGD passed on Civil and Gen
    # answered "Wrong Field" to the identical payload. Keep one case per
    # product so Civil's evidence does not bless Gen's behaviour.
    pogd_args = (
        PushoverAnalysisControlData, pogd_created, pogd_updated,
        lambda p: p["NONL_OPT"]["MAXITER"], 10, 11,
    )
    return [
        Case(
            AssignPushoverHingeProperties, phge_created, phge_updated,
            lambda p: p["ID"], 1, 2,
        ),
        Case(*pogd_args, products=("gen",)),
        Case(*pogd_args, products=("civil",), confirmed=True),
        Case(
            PushoverAnalysisControlDataHyperS, {}, pogd_m1_updated,
            lambda p: p["ITER_CTRL"]["MAX_ITER"], None, 31,
            products=("civil",), confirmed=True,
        ),
    ]


def _tdnt_payload(name: str, *, ase: float) -> Dict[str, Any]:
    """The ch07 section 6 request example: KSCE LSD15, internal post-tension.

    The contract marks FT, FPK and TDMFNAME required with no condition, but
    the manual's own relaxation-code table scopes each to a different RM
    group, and its worked example - RM 6, KSCE LSD15 - sends none of the
    three. Send the example as written rather than invent a value for a field
    this code does not use.
    """
    return {
        "NAME": name,
        "TYPE": "INTERNAL",
        "MATL": 1,
        "AREA": 0.00504,
        "D_AREA": 0.1,
        "RM": 6,
        "RV": 2,
        "US": 1860000,
        "YS": 1570000,
        "LT": "POST",
        "ASB": 0.006,
        "ASE": ase,
        "bBONDED": True,
        "FF": 0.3,
        "WF": 0.0066,
    }


def _tdna_payload(name: str, *, xar_angle: float) -> Dict[str, Any]:
    """The ch07 section 7 2D spline example, on the base model's own beams.

    The example places the tendon on elements 101-105, which no fixture model
    has; the shared base model's three beams carry it instead - the same
    remapping the ch08 lane fixtures already do onto its plate corners. bPJ
    is sent because the CURVE variant declares it and every manual CURVE
    example includes it. This is the SPLINE branch, so no RADIUS: that field
    belongs to ROUND, where a 2026-09-18 live check confirmed it is a Number
    rather than the Boolean or Array two of the manual's own rows claim.
    """
    return {
        "NAME": name,
        "TDN_PROP": 1,
        "ELEM": [1, 2, 3],
        "BELENG": 0,
        "ELENG": 0,
        "CURVE": "SPLINE",
        "INPUT": "2D",
        "TDN_GRUP": 1,
        "LENG_OPT": "AUTO2",
        "bTP": False,
        "SHAPE": "ELEMENT",
        "INS_PT": "END-I",
        "INS_ELEM": 1,
        "AXIS_IJ": "I-J",
        "XAR_ANGLE": xar_angle,
        "bPJ": True,
        "OFF_YZ": [0, 0],
        "PROFY": [
            {"PT": [0, -0.5], "bFIX": True, "R": 0},
            {"PT": [15, -0.3], "bFIX": False, "R": 0},
            {"PT": [30, -0.5], "bFIX": True, "R": 0},
        ],
        "PROFZ": [
            {"PT": [0, -0.6], "bFIX": True, "R": 0, "bBOTZ": False},
            {"PT": [15, -0.3], "bFIX": False, "R": 0, "bBOTZ": False},
            {"PT": [30, -0.6], "bFIX": True, "R": 0, "bBOTZ": False},
        ],
    }


def _tdpl_payload(*, end: float) -> Dict[str, Any]:
    """The ch07 section 9 request example, against this tier's own records.

    The example's "PS" load case and "T1_Profile_2D" tendon are names it
    assumes exist; point them at the seeds instead of creating a second set.
    """
    return {
        "ITEMS": [
            {
                "ID": 1,
                "LCNAME": "PS18_SEED",
                "GROUP_NAME": "",
                "TENDON_NAME": "TDNA_SEED",
                "TYPE": "FORCE",
                "ORDER": "BOTH",
                "BEGIN": 1360000,
                "END": end,
                "GROUTING": 1,
            }
        ]
    }


def _extras18_seeds() -> List[SeedStep]:
    """The chain ch07 documents: load case -> property -> profile.

    Its own prestress load case rather than extras15's: /db/STLD renumbers,
    and two tiers owning one id is exactly what made /db/SPLC and /db/MVCD
    collide across tiers.
    """
    return [
        SeedStep(
            "tdpl_prestress_case",
            lambda client: StaticLoadCase.create(
                {17: {"NAME": "PS18_SEED", "TYPE": "PS", "DESC": "tendon fixture"}},
                client=client,
            ),
        ),
        SeedStep(
            "tdnt_seed",
            lambda client: TendonProperty.create(
                {1: _tdnt_payload("TDNT_SEED", ase=0.006)}, client=client,
            ),
        ),
        # The TDNA example's TDN_GRUP 1 names a tendon group it assumes
        # exists; on 2026-09-19 Gen answered "[Error] Tendon Group 1 does not
        # exist." through npm - the shape accepted, the target missing. The
        # payload is extras1's confirmed /db/TDGR case, which takes id 1 and
        # deletes it before this tier runs.
        SeedStep(
            "tdgr_seed",
            lambda client: TendonGroup.create(
                {1: {"NAME": "TDGR_SEED"}}, client=client,
            ),
        ),
        SeedStep(
            "tdna_seed",
            lambda client: TendonProfile.create(
                {1: _tdna_payload("TDNA_SEED", xar_angle=0)}, client=client,
            ),
        ),
    ]


def _extras18_cases() -> List[Case]:
    """Task A: ch07's tendon chain, each case beside the record the next needs.

    Every case takes an id the seeds do not own, so a case deleting itself
    cannot take a later case's prerequisite with it.
    """
    return [
        # Passed through both SDKs on Gen and Civil, Build 09/15/2026,
        # 2026-09-19 - the manual's example as written, with no FT/FPK/TDMFNAME.
        Case(
            TendonProperty,
            _tdnt_payload("T1_Post_KSCE", ase=0.006),
            _tdnt_payload("T1_Post_KSCE", ase=0.012),
            lambda p: p.get("ASE"), 0.006, 0.012,
            item_id=2, confirmed=True,
        ),
        # 2026-09-19, both SDKs, both products: with the tendon group seeded,
        # the product answers "[Error] Errors detected in Tendon Profile
        # Data.(Item:IS_DB_TDNA_NOTENSIONCALC : Not Registered String)" - the
        # shape is accepted, and the message is an unregistered resource-string
        # id rather than text. Unconfirmed until what "no tension calc" needs
        # of the model is established; do not permute fields to find out.
        Case(
            TendonProfile,
            _tdna_payload("T1_Profile_2D", xar_angle=0),
            _tdna_payload("T1_Profile_2D", xar_angle=15),
            lambda p: p.get("XAR_ANGLE"), 0, 15,
            item_id=2, needs=("tdnt_seed", "tdgr_seed"),
        ),
        Case(
            TendonPrestress,
            _tdpl_payload(end=1360000),
            _tdpl_payload(end=1200000),
            lambda p: p["ITEMS"][0]["END"], 1360000, 1200000,
            item_id=1,
            needs=("tdpl_prestress_case", "tdnt_seed", "tdgr_seed", "tdna_seed"),
        ),
    ]


def _extras19_seeds() -> List[SeedStep]:
    """Build the ch07 prerequisites for the manual's PTNS example.

    PTNS is keyed by a truss/cable element and the shared base model has only
    beams and a plate, so element 5 gets the official ch03 TRUSS shape on its
    own node pair.  The load case and its EXLD registration come from ch07
    sections 11-12.

    Every step here is this tier's own.  The tier runner executes *all* of a
    selected tier's seeds before its cases, not just the ones a case declares,
    so splicing another tier's seed list - as this tier did until 2026-09-20 -
    POSTs that seed twice whenever both tiers are selected, which is what a
    full re-verification does.  /db/STLD renumbers, so the second POST of
    extras15's records would have left two load cases answering to the same
    name the fixture looks up.  Nodes 21-22 are likewise off limits: the base
    model keeps that pair unattached so ELNK, RIGD and MCON cannot collide
    with a real element.
    """
    return [
        SeedStep(
            "ptns_nodes",
            lambda client: Node.create(
                {
                    51: {"X": -BAY, "Y": 0, "Z": 0},
                    52: {"X": -BAY, "Y": 0, "Z": HEIGHT},
                },
                client=client,
            ),
        ),
        SeedStep(
            "ptns_truss",
            lambda client: Element.create(
                {5: {
                    "TYPE": "TRUSS", "MATL": 1, "SECT": 1,
                    "NODE": [51, 52], "ANGLE": 0,
                }},
                client=client,
            ),
        ),
        SeedStep(
            "ptns_load_case",
            lambda client: StaticLoadCase.create(
                {19: {"NAME": "PS19_SEED", "TYPE": "PS",
                      "DESC": "pretension fixture"}},
                client=client,
            ),
        ),
        # extras15's own /db/EXLD case owns id 1 too, and deletes it as the
        # last step of its round trip. extras15 runs first because TIERS is
        # ordered, so this seed re-creates a record that is already gone.
        SeedStep(
            "ptns_external_load_case",
            lambda client: ExternalLoadCaseForPretension.create(
                {1: {"LCNAME_ITEM": ["PS19_SEED"]}}, client=client,
            ),
        ),
    ]


def _extras19_cases() -> List[Case]:
    """Task P: the manual's pretension load on a seeded truss element."""
    return [
        Case(
            PretensionLoad,
            {"ITEMS": [{
                "ID": 1, "LCNAME": "PS19_SEED", "GROUP_NAME": "",
                "TENSION": 130,
            }]},
            {"ITEMS": [{
                "ID": 1, "LCNAME": "PS19_SEED", "GROUP_NAME": "",
                "TENSION": 260,
            }]},
            lambda payload: payload["ITEMS"][0].get("TENSION"),
            130,
            260,
            item_id=5,
            needs=(
                "ptns_nodes", "ptns_truss", "ptns_load_case",
                "ptns_external_load_case",
            ),
            confirmed=True,
        ),
    ]


# 2026-09-05, both public SDKs on disposable base models; see live notes.
# These are payload/code-specific observations, not endpoint product gates.
_LANE_LIVE_CONFIRMED = {
    "/db/LLANch": {"civil"},
    "/db/LLANid": {"civil"},
    "/db/LLANtr": {"civil", "gen"},
    "/db/LLANop": {"civil"},
    "/db/SLAN": {"civil", "gen"},
    "/db/SLANch": {"civil"},
    "/db/SLANop": {"civil"},
}


def _manual_lane_cases(resources, code: str, products=None) -> List[Case]:
    """Replay ch08 sections 3-9's JSON examples with existing model IDs.

    The snapshot is extracted from the manual, not an SDK. Surface paths
    attach to the base model's plate corners (5-8). The update changes the
    first eccentricity/offset to its documented default 0; transverse lanes
    use the documented factor itself for a write/read/idempotence check.
    """
    path = Path(__file__).parent / "fixtures" / "lane_manual_examples.json"
    examples = json.loads(path.read_text(encoding="utf-8"))["examples"]
    cases = []
    for resource in resources:
        payload = copy.deepcopy(examples[resource.ENDPOINT])
        if code == "BS":
            # The manual examples' 1.8/1.8288 spacing is rejected under BS
            # on Gen (2026-09-05). Try this field's own documented default,
            # not an invented wheel count or a different lane width.
            payload["WHEEL_SPACE"] = 0
        entries_key = "ITEMS" if "ITEMS" in payload else "LANE_ITEMS"
        entries = payload[entries_key]
        surface = resource.ENDPOINT.startswith("/db/SLAN")
        if surface:
            node_key = "NODE_KEY" if entries_key == "ITEMS" else "NODE"
            for index, entry in enumerate(entries):
                entry[node_key] = 5 + index
        probe_key = "OFFSET" if surface else "ECC"
        if resource.ENDPOINT == "/db/LLANtr":
            probe_key = "FACTOR"
        updated = copy.deepcopy(payload)
        if probe_key != "FACTOR":
            updated[entries_key][0][probe_key] = 0
        for product in products or ("gen", "civil"):
            cases.append(Case(
                resource, copy.deepcopy(payload), copy.deepcopy(updated),
                lambda p, key=entries_key, field=probe_key: p[key][0][field],
                entries[0][probe_key], updated[entries_key][0][probe_key],
                item_id=1, confirmed=product in _LANE_LIVE_CONFIRMED[resource.ENDPOINT],
                products=(product,), needs=(f"lane_code_{code}",),
            ))
    return cases


def _lane_code_seed(code: str, products=None) -> List[SeedStep]:
    """Select the moving-load code, whether or not another tier already did.

    CODE literals are from ch08 section 1's CODE value table.

    Every lane tier seeds this same /db/MVCD record with a different CODE, so
    a POST answers `Key Already Exist` for every tier after the first and
    blocks its whole tier -- confirmed live 2026-09-06 on Gen, where selecting
    four lane tiers together left one running and blocked five cases. The
    record is a single-row selector rather than a table, so a PUT is what
    changing it means; /db/MVCD declares PUT.
    """
    def select(client: MidasClient) -> None:
        records = {1: {"CODE": code}}
        try:
            MovingLoadCode.create(records, client=client)
        except MidasAPIError:
            # Deliberately POST first and fall back, rather than reading the
            # record and branching. A seed that reads state back cannot be
            # replayed from an emitted payload, so branching here would take
            # all thirteen ch08 cases away from the npm harness to fix a
            # Python-only collision.
            MovingLoadCode.update(records, client=client)

    return [SeedStep(f"lane_code_{code}", select, products=products)]


def _moving_manual_body(endpoint: str, block: int = 0) -> dict:
    path = Path(__file__).parent / "fixtures" / "moving_aux_manual_examples.json"
    examples = json.loads(path.read_text(encoding="utf-8"))["examples"]
    return copy.deepcopy(examples[endpoint][block]["Assign"])


def _moving_control_manual_body(endpoint: str) -> dict:
    """Return a ch12 moving-load-control record from the vendored manual."""
    path = Path(__file__).parent / "fixtures" / "moving_control_manual_examples.json"
    examples = json.loads(path.read_text(encoding="utf-8"))["examples"]
    return copy.deepcopy(examples[endpoint]["1"])


def _moving_control_cases(resource, code: str, products=None) -> List[Case]:
    """Replay one complete ch12 JSON example without inventing update values."""
    payload = _moving_control_manual_body(resource.ENDPOINT)
    probe_key = "LOAD_POINT_SEL" if resource is MovingLoadAnalysisControlTransverse else "iIGP"
    return [Case(
        resource, copy.deepcopy(payload), copy.deepcopy(payload),
        lambda p, key=probe_key: p[key], payload[probe_key], payload[probe_key],
        products=(product,), confirmed=True, needs=(f"lane_code_{code}",),
    ) for product in products or ("gen", "civil")]


def _moving_case_manual_body(endpoint: str) -> dict:
    """Return ch08's first complete country/code-specific load-case record."""
    path = Path(__file__).parent / "fixtures" / "moving_case_manual_examples.json"
    examples = json.loads(path.read_text(encoding="utf-8"))["examples"]
    return copy.deepcopy(examples[endpoint]["1"])


def _moving_case_lane_seed(
    name: str, resource, lane_names: Sequence[str], *, generic: bool = False,
) -> SeedStep:
    """Clone a manual lane example under the names referenced by a case.

    Only the record id and ``LL_NAME`` are remapped. Both values come from the
    target section's own Request Body; the lane's fields stay byte-for-byte
    with the vendored manual example. POST-then-PUT keeps the seed replayable
    when several code tiers share /db/LLAN in one product session.
    """
    if generic:
        template = next(iter(_moving_manual_body("/db/LLAN").values()))
    else:
        path = Path(__file__).parent / "fixtures" / "lane_manual_examples.json"
        examples = json.loads(path.read_text(encoding="utf-8"))["examples"]
        template = examples[resource.ENDPOINT]
    records = {}
    for item_id, lane_name in enumerate(lane_names, start=1):
        payload = copy.deepcopy(template)
        payload["COMMON"]["LL_NAME"] = lane_name
        records[item_id] = payload

    def seed(client: MidasClient) -> None:
        try:
            resource.create(records, client=client)
        except MidasAPIError:
            resource.update(records, client=client)

    return SeedStep(name, seed)


#: The vehicle each country case's sub-load names, from ch08 section 10's own
#: examples. On 2026-09-19 MVLDch answered "Non-existent Vehicle has been
#: defined in Sub-Load Case" and MVLDid "Number of Sub-Load Cases": neither
#: case's needs built a vehicle at all.
#:
#: India is paired by the manual itself - section 14's General Load Python
#: example names ``IN(IRC6)_ClassA``, which is section 10's India Class A
#: example - so the case takes that example's name in place of the Request
#: Body's railway vehicle, which no section documents creating.  China has
#: no such pairing: sections 13's examples both name the standard class
#: ``CH(CJJ11)_C-CD(A/B)``, which no section documents creating, and the only
#: China vehicle section 10 documents is the user-defined ``CN_UD_Lane1``.
#: The case names that one - a model reference remapped, as the element and
#: lane references already are, not a value invented.
_MOVING_CASE_VEHICLES: Dict[str, Tuple[str, Dict[str, Any]]] = {
    "CHINA": ("VEHICLE_CLASS", {
        "MVLD_CODE": 3,
        "VEHICLE_LOAD_NAME": "CN_UD_Lane1",
        "VEHICLE_LOAD_NUM": 2,
        "USER_LOAD_TYPE": "Truck/Lane",
        "VEH_CN": {"TRUCK_TYPE": 0, "P_": 130, "QM": 10.5, "QQ": 7},
    }),
    "INDIA": ("VEHICLE_CLASS_1", {
        "MVLD_CODE": 7,
        "VEHICLE_LOAD_NAME": "IN(IRC6)_ClassA",
        "VEHICLE_LOAD_NUM": 1,
        "VEHICLE_TYPE_NAME": "ClassA",
        "STANDARD_CODE": "IRC:6-2000",
    }),
}


#: 2026-09-19, Build 09/15/2026, both public SDKs: full round trips on Civil
#: once each case's vehicle was seeded - MVLDid's "Number of Sub-Load Cases"
#: had been the missing vehicle too, and NUM_LOADED_LANES was left alone.
_MOVING_CASE_CONFIRMED = {"CHINA": {"civil"}, "INDIA": {"civil"}}


def _moving_case_vehicle_seed(code: str, products=None) -> SeedStep:
    _, vehicle = _MOVING_CASE_VEHICLES[code]
    return SeedStep(
        f"moving_case_vehicle_{code}",
        lambda c, v=vehicle: Vehicles.create({1: copy.deepcopy(v)}, client=c),
        products,
    )


def _moving_country_case(resource, code: str, products=None) -> List[Case]:
    """One ch08 country load case, on the lanes and vehicle it names.

    The update changes DESC alone - the same probe /db/STLD's confirmed case
    uses - because a case whose update equals its create proves nothing
    about a PUT; that was Task G.
    """
    payload = _moving_case_manual_body(resource.ENDPOINT)
    needs: Tuple[str, ...] = (f"lane_code_{code}", f"moving_case_lanes_{code}")
    if code in _MOVING_CASE_VEHICLES:
        key, vehicle = _MOVING_CASE_VEHICLES[code]
        for item in payload.get("SUB_LOAD_ITEMS", []):
            item[key] = vehicle["VEHICLE_LOAD_NAME"]
        needs += (f"moving_case_vehicle_{code}",)
    updated = copy.deepcopy(payload)
    updated["DESC"] = "crud updated"
    return [Case(
        resource, copy.deepcopy(payload), updated,
        lambda p: p.get("DESC"), payload["DESC"], "crud updated",
        products=(product,), needs=needs,
        confirmed=product in _MOVING_CASE_CONFIRMED.get(code, set()),
    ) for product in products or ("gen", "civil")]


def _moving_case_lane_seeds(
    code: str, resource, lane_names: Sequence[str], products=None, *, generic=False,
) -> List[SeedStep]:
    lane = _moving_case_lane_seed(
        f"moving_case_lanes_{code}", resource, lane_names, generic=generic,
    )
    if products:
        lane.products = frozenset(products)
    return _lane_code_seed(code, products) + [lane]


def _dynamic_hypers_cases() -> List[Case]:
    """Replay ch09's complete PUT-only Hyper-S control examples."""
    path = Path(__file__).parent / "fixtures" / "dynamic_hypers_manual_examples.json"
    examples = json.loads(path.read_text(encoding="utf-8"))["examples"]
    cases = []
    for resource, probe in (
        (TimeHistoryGlobalControlHyperS, ("GEO_NONL_TYPE", 1)),
        (TimeHistoryOutputOptionHyperS, ("OUT_OPT", {
            "HINGE_OUT": 1, "COMMON_OPT": False, "FIBER_OUT": 1,
        })),
    ):
        payload = copy.deepcopy(examples[resource.ENDPOINT]["1"])
        key, expected = probe
        cases.append(Case(
            resource, copy.deepcopy(payload), copy.deepcopy(payload),
            lambda p, field=key: p[field], expected, expected,
            confirmed=True, products=("civil",),
        ))
    return cases


def _moving_aux_cases() -> List[Case]:
    # Source JSON snapshots retain the original IDs. Only model references
    # are remapped: beam 2, supported node 1, and plate 4 already exist.
    mlsp_records = _moving_manual_body("/db/MLSP", 1)
    mlsp = copy.deepcopy(mlsp_records["1"])
    mlsp["ELEMENT_NO"] = 2
    mlsp_updated = copy.deepcopy(mlsp)
    mlsp_updated["POSITION"] = mlsp_records["2"]["POSITION"]
    mlsr = next(iter(_moving_manual_body("/db/MLSR").values()))
    sinf = next(iter(_moving_manual_body("/db/SINF").values()))
    sinf["ELEM_LISTS"] = [4]
    return [
        Case(LaneSupportNegativeMoment, mlsp, mlsp_updated,
             lambda p: p["POSITION"], mlsp["POSITION"], mlsp_updated["POSITION"],
             confirmed=True, needs=("lane_code_AASHTO LRFD",)),
        Case(LaneSupportReaction, mlsr, copy.deepcopy(mlsr),
             lambda p: p["NODE"], mlsr["NODE"], mlsr["NODE"],
             confirmed=True, needs=("lane_code_AASHTO LRFD",)),
        Case(PlateElementForInfluenceSurface, sinf, copy.deepcopy(sinf),
             lambda p: p["ELEM_LISTS"], sinf["ELEM_LISTS"], sinf["ELEM_LISTS"],
             needs=("lane_code_AASHTO LRFD",)),
    ]


def _transverse_vehicle_cases() -> List[Case]:
    # Both products reject the manual's first, median-disabled example.
    # Test its second complete example independently, without filling in
    # unstated values for the omitted median fields.
    payload = _moving_manual_body("/db/MVHLtr")["2"]
    updated = copy.deepcopy(payload)
    updated["DE"] = 0  # section 11's documented default
    return [Case(VehiclesTransverse, payload, updated, lambda p: p["DE"],
                 payload["DE"], 0, confirmed=True, needs=("lane_code_TRANS",))]


def _impact_seeds() -> List[SeedStep]:
    return _lane_code_seed("KOREA") + [
        SeedStep("impact_manual_lane", lambda c: TrafficLineLanes.create(
            _moving_manual_body("/db/LLAN"), client=c)),
    ]


def _impact_cases() -> List[Case]:
    payload = next(iter(_moving_manual_body("/db/IMPF").values()))
    # Section 26's first example is an element-keyed impact factor; keep the
    # manual value and verify idempotent PUT, without inventing a new factor.
    return [Case(AdditionalImpactFactor, copy.deepcopy(payload), copy.deepcopy(payload),
                 lambda p: p["ITEMS"][0]["FACTOR"], 0.3, 0.3, item_id=2,
                 products=(product,), confirmed=product == "civil",
                 needs=("lane_code_KOREA", "impact_manual_lane"))
            for product in ("gen", "civil")]


def _transverse_load_seeds() -> List[SeedStep]:
    return _lane_code_seed("TRANS") + [
        SeedStep("transverse_case_lane", lambda c: TrafficLineLanesTransverse.create(
            {1: _manual_lane_cases([TrafficLineLanesTransverse], "TRANS")[0].create_payload},
            client=c)),
        SeedStep("transverse_case_vehicle", lambda c: VehiclesTransverse.create(
            {1: _transverse_vehicle_cases()[0].create_payload}, client=c)),
    ]


def _transverse_load_cases() -> List[Case]:
    payload = _moving_manual_body("/db/MVLDtr")["1"]
    # Bind the manual's vehicle reference to its median-enabled example,
    # which actually passed; do not use the rejected basic example as a seed.
    payload["MVHL_NAME"] = _transverse_vehicle_cases()[0].create_payload["NAME"]
    # Confirmed on both products 2026-09-06. It had been blocked on Gen by the
    # /db/MVCD seed collision above, not by anything about this endpoint.
    return [Case(MovingLoadCaseTransverse, payload, copy.deepcopy(payload),
                 lambda p: p["LCNAME"], payload["LCNAME"], payload["LCNAME"],
                 confirmed=True,
                 needs=("lane_code_TRANS", "transverse_case_lane", "transverse_case_vehicle"))]


#: Priority order — what a modelling script needs, not the manual's order.
TIERS: List[Tier] = [
    Tier("lanes_china", "manual China line/surface lanes",
         lambda: _lane_code_seed("CHINA"),
         lambda: _manual_lane_cases([TrafficLineLanesChina, TrafficSurfaceLanesChina], "CHINA")),
    Tier("lanes_india", "manual India line lane",
         lambda: _lane_code_seed("INDIA"),
         lambda: _manual_lane_cases([TrafficLineLanesIndia], "INDIA")),
    Tier("lanes_transverse", "manual transverse line lane",
         lambda: _lane_code_seed("TRANS"),
         lambda: _manual_lane_cases([TrafficLineLanesTransverse], "TRANS")
         + _transverse_vehicle_cases()),
    Tier("lanes_optimization", "manual surface and optimization lanes",
         lambda: _lane_code_seed("KSCE-LSD15", ("civil",)),
         lambda: _manual_lane_cases([
             TrafficLineLanesOptimization, TrafficSurfaceLanes,
             TrafficSurfaceLanesOptimization,
         ], "KSCE-LSD15", ("civil",))),
    # ch08 lists BS for the general/optimization lane family. Gen refuses
    # KSCE-LSD15 at code selection (recorded 2026-07-29 and rechecked today).
    Tier("lanes_bs", "manual general/optimization lanes under Gen-available BS",
         lambda: _lane_code_seed("BS", ("gen",)),
         lambda: _manual_lane_cases([
             TrafficLineLanesOptimization, TrafficSurfaceLanes,
             TrafficSurfaceLanesOptimization,
         ], "BS", ("gen",))),
    Tier("moving_aux", "manual interior supports and influence-surface plate",
         lambda: _lane_code_seed("AASHTO LRFD"), _moving_aux_cases),
    Tier("moving_impact", "manual Korea lane impact factor", _impact_seeds, _impact_cases),
    Tier("moving_transverse_case", "manual transverse load case with real lane and vehicle",
         _transverse_load_seeds, _transverse_load_cases),
    Tier("moving_control_bs", "manual BS moving-load analysis control",
         lambda: _lane_code_seed("BS"),
         lambda: _moving_control_cases(MovingLoadAnalysisControlBS, "BS")),
    Tier("moving_control_india", "manual India moving-load analysis control",
         lambda: _lane_code_seed("INDIA", ("civil",)),
         lambda: _moving_control_cases(
             MovingLoadAnalysisControlIndia, "INDIA", ("civil",))),
    Tier("moving_control_transverse", "manual transverse moving-load analysis control",
         lambda: _lane_code_seed("TRANS"),
         lambda: _moving_control_cases(MovingLoadAnalysisControlTransverse, "TRANS")),
    Tier("moving_case_china", "manual China moving-load case",
         lambda: _moving_case_lane_seeds(
             "CHINA", TrafficLineLanesChina, ("LL_01", "LL_02"), ("civil",))
         + [_moving_case_vehicle_seed("CHINA", ("civil",))],
         lambda: _moving_country_case(MovingLoadCaseChina, "CHINA", ("civil",))),
    Tier("moving_case_india", "manual India moving-load case",
         lambda: _moving_case_lane_seeds(
             "INDIA", TrafficLineLanesIndia, ("LL_01", "LL_02"), ("civil",))
         + [_moving_case_vehicle_seed("INDIA", ("civil",))],
         lambda: _moving_country_case(MovingLoadCaseIndia, "INDIA", ("civil",))),
    Tier("moving_case_eurocode", "manual Eurocode moving-load case",
         lambda: _moving_case_lane_seeds(
             "EUROCODE", TrafficLineLanes,
             ("LL_01", "LL_02", "LL_03", "LL_04"), generic=True),
         lambda: _moving_country_case(MovingLoadCaseEurocode, "EUROCODE")),
    Tier("moving_case_poland", "manual Poland moving-load case",
         lambda: _moving_case_lane_seeds(
             "POLAND", TrafficLineLanes, ("L1", "L2"), ("civil",), generic=True),
         lambda: _moving_country_case(MovingLoadCasePoland, "POLAND", ("civil",))),
    Tier("dynamic_hypers_controls", "manual Hyper-S time-history controls",
         _no_seeds, _dynamic_hypers_cases),
    Tier("core", "baseline model, groups and static loads", _no_seeds, _core_cases),
    Tier("props", "material / section sub-types", _props_seeds, _props_cases),
    Tier("boundary", "springs and links", _boundary_seeds, _boundary_cases),
    Tier("static", "remaining static loads + temperature", _no_seeds, _static_cases),
    Tier("stage", "construction stages", _stage_seeds, _stage_cases),
    Tier("moving", "moving loads (AASHTO LRFD fixtures; confirmed both products)", _moving_seeds, _moving_cases),
    Tier("extras1", "batch 1 of read-only-verified db.project/db.boundary endpoints", _extras1_seeds, _extras1_cases),
    Tier("extras2", "batch 2: db.misc_loads in full + 3 of db.temperature_prestress", _extras2_seeds, _extras2_cases),
    Tier("extras3", "batch 3: tractable subset of db.properties.*", _extras3_seeds, _extras3_cases),
    Tier("extras4", "batch 4: db.load_combinations in full", _extras4_seeds, _extras4_cases),
    Tier("extras5", "batch 5: db.dynamic_loads (9 of 12, Hyper-S variants deferred)", _extras5_seeds, _extras5_cases),
    Tier("extras6", "batch 6: seismic-device family from db.boundary (SDVI/SDVE/SDST confirmed both products; SDHY/SDIS confirmed Gen-only; DRLS deferred)", _no_seeds, _extras6_cases),
    Tier("extras7", "batch 7: standalone/frame-attachable remainder of db.static_loads (PNLD/PNLA/FMLD/POSP/POSL confirmed; FBLA/EPST/EPSE fail live)", _extras7_seeds, _extras7_cases),
    Tier("extras8", "batch 8: tractable subset of db.analysis_control (PDEL/BUCK/SMCT/EIGV/BCCT/MVCT confirmed both products; HHCT/NLCT confirmed Gen only and fail on Civil; ACTL remains unresolved)", _extras8_seeds, _extras8_cases),
    Tier("extras9", "batch 9: db.node_element's Domain feature (MADO/SBDO/DOEL -- all 3 fail live, MADO silently drops writes on both products)", _extras9_seeds, _extras9_cases),
    Tier("extras10", "batch 10: standalone subset of db.construction_stage's heat-of-hydration family (ETFC/CCFC/HSFC/HAHS/STBK/HSTG confirmed; HAHS uses a real SOLID fixture; HPCE fails live; HECB/HSPT/CSCS deferred)", _extras10_seeds, _extras10_cases),
    Tier("extras11", "batch 11a/c: /db/STCT (fails live -- iITER/TOL silently don't persist), /db/HSPT and /db/HECB confirmed with a SOLID hydration fixture", _extras11_seeds, _extras11_cases),
    Tier("extras12", "batch 12: db.bridge in full, all 4 confirmed (GSBG/GCMB/CAMB Civil-only, ULFC both products)", _extras12_seeds, _extras12_cases),
    Tier("extras13", "batch 13: tractable non-rebar subset of db.design (7 confirmed both products; DSTL Civil-only success/Gen failure; RCHK/REBB/REBC/REBW/REBR deferred)", _no_seeds, _extras13_cases),
    Tier("extras14", "batch 14: the 12 Civil-only-by-design endpoints (5 db.moving_loads, 7 db.analysis_control Hyper-S/-M1), all confirmed", _extras14_seeds, _extras14_cases),
    Tier("extras15", "batch 15: tractable pushover and prestress assignments", _extras15_seeds, _extras15_cases),
    Tier("extras16", "batch 16: Task A properties with complete manual request values", _no_seeds, _extras16_cases),
    Tier("extras17", "batch 17: Task A pushover controls and hinge assignment", _no_seeds, _extras17_cases),
    Tier("extras18", "batch 18: Task A ch07 tendon chain (TDNT -> TDNA -> TDPL)", _extras18_seeds, _extras18_cases),
    Tier("extras19", "Task P: ch07 pretension load on a truss element", _extras19_seeds, _extras19_cases),
]


def apply_probe(case: "Case", record: Any, endpoint: str, label: str) -> Any:
    """Run a case's probe over a read-back record, as a case-level failure.

    A probe subscripts the record -- ``p["ITEMS"][0]["END"]`` -- so a record
    the product returns in another shape raises ``KeyError`` here rather than
    a ``MidasAPIError``. Uncaught, that escapes the tier loop and takes the
    report, the end-of-run checkpoint and the restore of an empty scratch
    document with it: the run is lost and the product is left holding the
    fixture's model. An unreadable record is a failure of this case and
    nothing more, which is what this converts it into.

    Module level so it can be tested without a live client; ``_run_case``'s
    ``read_probe`` closure is the only caller.
    """
    try:
        return case.probe(record)
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise MidasAPIError(
            f"{endpoint}: {label} probe could not read the record "
            f"({type(exc).__name__}: {exc})"
        ) from exc


def _run_case(case: Case, client: MidasClient) -> Dict[str, Any]:
    res = case.resource
    row: Dict[str, Any] = {
        "endpoint": res.ENDPOINT,
        "name": res.NAME,
        "id": case.item_id,
        "confirmed": case.confirmed,
        "steps": {},
    }

    def record(step: str, fn) -> Any:
        try:
            value = fn()
        except MidasAPIError as exc:
            row["steps"][step] = {"ok": False, "error": str(exc)[:200]}
            raise
        row["steps"][step] = {"ok": True}
        return value

    def read_probe(expected, label):
        got = res.items(client=client).get(case.item_id)
        if got is None:
            raise MidasAPIError(f"{res.ENDPOINT}: id {case.item_id} missing after {label}")
        actual = apply_probe(case, got, res.ENDPOINT, label)
        if actual != expected:
            raise MidasAPIError(
                f"{res.ENDPOINT}: {label} {expected!r}, read back {actual!r}"
            )
        return actual

    # A case whose id is already taken cannot say anything about its endpoint,
    # and calling that a regression is how a fixture collision reads as an SDK
    # defect. /db/SPLC is the confirmed case: extras4's Civil-only
    # lcom_seismic_splc seed occupies id 1, and extras5's Civil /db/SPLC case
    # owns the same id, so selecting both tiers answers "Key Already Exist" for
    # a shape both products accept when either tier runs alone. The npm harness
    # has refused a setup collision since it was written; this is the same
    # refusal on the side that had been reporting it as a regression.
    if "POST" in res.METHODS:
        try:
            occupied = case.item_id in res.items(client=client)
        except MidasAPIError:
            occupied = False
        if occupied:
            row["steps"]["create"] = {
                "ok": False,
                "error": (f"{res.ENDPOINT}: id {case.item_id} already exists before "
                          "this case ran; a seed in this selection owns it"),
            }
            row["ok"] = False
            row["classification"] = BLOCKED
            return row

    try:
        if "POST" in res.METHODS:
            record("create", lambda: res.create({case.item_id: case.create_payload},
                                                client=client))
            record("read_back", lambda: read_probe(case.expect_created, "wrote"))
        else:
            row["steps"]["create"] = {"ok": True, "skipped": "endpoint has no POST"}

        if "PUT" in res.METHODS:
            record("update", lambda: res.update({case.item_id: case.update_payload},
                                                client=client))
            record("read_updated", lambda: read_probe(case.expect_updated, "updated to"))
        else:
            row["steps"]["update"] = {"ok": True, "skipped": "endpoint has no PUT"}

        if "DELETE" in res.METHODS:
            record("delete", lambda: res.delete([case.item_id], client=client))

            def check_deleted():
                if case.item_id in res.items(client=client):
                    raise MidasAPIError(
                        f"{res.ENDPOINT}: id {case.item_id} still present after delete"
                    )
                return True

            record("read_deleted", check_deleted)
        else:
            row["steps"]["delete"] = {"ok": True, "skipped": "endpoint has no DELETE"}
    except MidasAPIError:
        pass

    row["ok"] = all(step.get("ok") for step in row["steps"].values())
    row["classification"] = OK if row["ok"] else (REGRESSION if case.confirmed
                                                  else UNVERIFIED)
    return row


def _session_lost(row: Dict[str, Any]) -> bool:
    """Did this failure mean the product is gone, rather than that the call
    was rejected?

    Learned the hard way on 2026-07-26: Civil NX died mid-run, and the run
    then spent two 30s timeouts and six 404s grinding through cases that
    never had a chance. The relay answers ``404 client does not exist`` once
    the process is gone, and a read timeout is what you get while it is
    dying. Either way there is nothing left to test, so stop and say so —
    reporting 8 "failures" against a corpse is exactly the false-positive
    noise this report is built to avoid.
    """
    for step in row["steps"].values():
        error = str(step.get("error", ""))
        if "client does not exist" in error or "Read timed out" in error:
            return True
    return False


def _stub_row(case: Case, classification: str, reason: str) -> Dict[str, Any]:
    return {
        "endpoint": case.resource.ENDPOINT,
        "name": case.resource.NAME,
        "id": case.item_id,
        "confirmed": case.confirmed,
        "steps": {},
        "ok": False,
        "classification": classification,
        "blocked_by": reason,
    }


def _mark(row: Dict[str, Any]) -> str:
    return {OK: "PASS", REGRESSION: "REGRESS", UNVERIFIED: "FAIL",
            BLOCKED: "BLOCK", SKIPPED: "SKIP"}[row["classification"]]


#: Seeds the products renumber to the next free id instead of honouring the
#: requested "Assign" key -- confirmed live 2026-08-16, see _extras5_seeds().
#: The npm harness verifies these by NAME rather than by id.  Nothing else is
#: listed: renumbering is a live observation, never something to assume for a
#: seed nobody has watched.
RENUMBERING_SEEDS = frozenset({
    "dl14_seed", "fbld7_seed", "pnld_seed", "prestress_load_cases",
    "ptns_load_case", "smpt_seed", "spfc_seed", "tdpl_prestress_case",
    "thfc_seed", "thfc_force_seed", "this_seed",
})

#: Seeds whose one read only guards against a record an *earlier Python tier*
#: already created, so a full run does not POST a duplicate.  The npm harness
#: starts every run from the emitted base model, where that record never
#: exists, so the create branch is the one it needs -- and if it ever does
#: exist, the harness's setup-collision check refuses loudly rather than
#: overwriting it.  The recorder answers such a seed's GET with an empty table
#: and exports what follows.  Nothing else is listed: a seed that branches on
#: what the *product* put in a fresh document is a different thing, and
#: exporting one branch of it would be a guess.
FRESH_DOCUMENT_SEEDS = frozenset({"stage11_seed"})


def _exportable_tier_seeds() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Export every tier seed the shared fixture can express, and name the rest.

    Capture each step's own calls; never reconstruct its payload.  The boundary
    is mechanical rather than a list of tiers someone happened to look at: a
    seed the npm harness can replay is a **sequence of ``{"Assign": ...}``
    POSTs and per-id ``DELETE {endpoint}/{id}`` calls**, because those are the
    two step shapes ``setupRecords`` in live-crud.mjs sends, in order.  A
    delete step is what ``DbResource.delete`` issues, one id per URL; it is
    exported as ``{"endpoint": ..., "delete": [ids]}``.  A seed that reads
    state back cannot be replayed from an emitted payload, unless it is one of
    the ``FRESH_DOCUMENT_SEEDS`` whose read only exists for a full Python run.

    Returns the exportable seeds and, separately, a reason for each seed that
    cannot be expressed.  An unexportable seed must stay **visible**.  Dropping
    it silently is what let the npm harness run a case half-seeded, and a
    half-seeded case fails in a way that looks exactly like an SDK defect --
    the one thing this harness exists not to do.
    """
    class Recorder(MidasClient):
        def __init__(self, product: str, *, fresh_document: bool) -> None:
            super().__init__(mapi_key="offline-fixture", product=product)
            self.calls: List[Dict[str, Any]] = []
            self.fresh_document = fresh_document

        def request(self, method, command, body=None, **kwargs):  # type: ignore[override]
            if method == "GET" and self.fresh_document and body is None:
                return {}
            if method == "DELETE" and body is None:
                endpoint, _, key = command.rpartition("/")
                if not endpoint.startswith("/db/") or not key.isdigit():
                    raise ValueError(f"{method} {command} is not a per-id DELETE")
                previous = self.calls[-1] if self.calls else None
                if previous and previous.get("endpoint") == endpoint and "delete" in previous:
                    previous["delete"].append(key)
                else:
                    self.calls.append({"endpoint": endpoint, "delete": [key]})
                return {}
            if method != "POST" or not isinstance(body, dict) or set(body) != {"Assign"}:
                raise ValueError(f"{method} {command} is not an Assign POST or a per-id DELETE")
            self.calls.append({"endpoint": command, "records": body["Assign"]})
            return {}

    def record(step: SeedStep) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        # A product-gated seed is still exportable; try the products the step
        # itself declares rather than reporting a product gate as a shape
        # problem.
        reason = "declares no product"
        for product in sorted(step.products):
            recorder = Recorder(product, fresh_document=step.name in FRESH_DOCUMENT_SEEDS)
            try:
                step.run(recorder)
            except Exception as exc:  # noqa: BLE001 - the message is the payload
                reason = f"{type(exc).__name__}: {exc}"[:160]
                continue
            if not recorder.calls:
                return None, "issued no request"
            return recorder.calls, ""
        return None, reason

    seeds: Dict[str, Dict[str, Any]] = {}
    unsupported: Dict[str, str] = {}
    for tier in TIERS:
        for step in tier.seeds():
            calls, reason = record(step)
            if calls is None:
                if step.name in seeds:
                    raise ValueError(
                        f"tier seed {step.name!r} is both replayable and unsupported; "
                        "global fixture names cannot represent both"
                    )
                previous_reason = unsupported.get(step.name)
                if previous_reason is not None and previous_reason != reason:
                    raise ValueError(
                        f"duplicate unsupported tier seed {step.name!r} has different "
                        "failure reasons"
                    )
                unsupported.setdefault(step.name, reason)
                continue
            if step.name in RENUMBERING_SEEDS:
                for call in calls:
                    if "records" in call:
                        call["allowRenumbering"] = True
            # One POST keeps the flat shape BASE_MODEL_SEEDS also uses; more
            # than one is a "steps" list the npm side replays in order.
            exported = calls[0] if len(calls) == 1 else {"steps": calls}
            if step.name in unsupported:
                raise ValueError(
                    f"tier seed {step.name!r} is both unsupported and replayable; "
                    "global fixture names cannot represent both"
                )
            previous = seeds.get(step.name)
            if previous is not None and previous != exported:
                raise ValueError(
                    f"duplicate tier seed name {step.name!r} carries different "
                    "payloads; global fixture names must identify one payload"
                )
            seeds.setdefault(step.name, exported)
    return seeds, unsupported


def _declared_seeds(case: Case) -> Set[str]:
    """Seed names a case already names in its own ``setup``, or replaces there."""
    return {step["seed"] for step in case.setup
            if isinstance(step, dict) and isinstance(step.get("seed"), str)
            } | set(case.setup_replaces)


def _live_cases_fixture() -> Dict[str, Any]:
    """Return the language-neutral source for Python and npm live checks.

    This is deliberately derived from the canonical ``Case`` objects rather
    than being a second, hand-maintained copy.  The npm harness does not import
    this Python module; it reads the committed JSON emitted here.
    """
    shared_seeds, unsupported_seeds = _exportable_tier_seeds()
    # BASE_MODEL_SEEDS is hand-curated and referenced by name from cases' own
    # setup, so it wins a name collision with an exported tier seed. One name
    # collides today: lcom_seismic_splc, whose tier step is the SPFC+SPLC pair
    # that /db/LCOM-SEISMIC already spells out as two separate setup entries.
    # tests/test_live_cases.py pins both halves of that.
    all_seeds = {**shared_seeds, **BASE_MODEL_SEEDS}
    cases: List[Dict[str, Any]] = []
    for tier in TIERS:
        for case in tier.cases():
            resource = case.resource
            cases.append({
                "tier": tier.name,
                "endpoint": resource.ENDPOINT,
                "name": resource.NAME,
                "id": case.item_id,
                "products": list(case.products),
                "methods": sorted(resource.METHODS),
                "confirmed": case.confirmed,
                "createPayload": case.create_payload,
                "updatePayload": case.update_payload,
                "expected": {
                    "created": case.expect_created,
                    "updated": case.expect_updated,
                    # Only written when set, so the other cases' entries stay
                    # byte-identical.
                    **({"unordered": True} if case.unordered else {}),
                },
                "needs": list(case.needs),
                # A case that already spells out a seed keeps its own ordering;
                # only the needs it never expressed as setup are prepended.
                "setup": [
                    {"seed": name} for name in case.needs
                    if name in all_seeds and name not in _declared_seeds(case)
                ] + list(case.setup),
                # Needs this fixture cannot express as a replayable POST, and
                # that the case does not already spell out itself. The npm
                # harness must report such a case blocked, exactly as the
                # Python runner reports a case whose seed step failed -- never
                # run it with the setup silently shortened.
                "blockedSeeds": [
                    n for n in case.needs
                    if n not in all_seeds and n not in _declared_seeds(case)
                ],
                "crashes": case.crashes,
            })
            unknown = [n for n in case.needs
                       if n not in all_seeds and n not in unsupported_seeds]
            if unknown:
                raise ValueError(
                    f"{resource.ENDPOINT}: needs {unknown}, which names no seed "
                    "step in any tier. A need resolving to nothing would emit "
                    "an incomplete setup that no reader could see."
                )
    fixture = {
        "version": LIVE_CASES_VERSION,
        "seeds": all_seeds,
        # Named, with the reason, so a harness can refuse a case instead of
        # guessing why its preconditions are missing.
        "unsupportedSeeds": unsupported_seeds,
        # The model every case attaches to, in the order it must be built.
        # Without it a harness starting from an empty /doc/NEW cannot resolve
        # any case's node/element/material/section preconditions, which is
        # what the npm side hit.
        "baseModel": [
            {
                "endpoint": step["resource"].ENDPOINT,
                "method": step["method"],
                # Ids are ints in BASE_MODEL_STEPS because that reads better
                # beside the payloads; JSON has only string keys, so stringify
                # here or --check-cases sees drift on every run.
                "records": {str(k): v for k, v in step["records"].items()},
            }
            for step in BASE_MODEL_STEPS
        ],
        "cases": cases,
    }
    # Fail at generation time if a future Case grows a non-JSON wire value.
    json.dumps(fixture, ensure_ascii=False, sort_keys=True)
    return fixture


def _write_live_cases(path: Path) -> None:
    path.write_text(
        json.dumps(_live_cases_fixture(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _check_live_cases(path: Path) -> bool:
    """Return whether the checked-in npm fixture matches the Python cases."""
    try:
        actual = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Missing live-case fixture: {path}", file=sys.stderr)
        return False
    except json.JSONDecodeError as exc:
        print(f"Invalid live-case fixture {path}: {exc}", file=sys.stderr)
        return False
    expected = _live_cases_fixture()
    if actual == expected:
        return True
    print(
        f"Live-case fixture drifted: run python scripts/live_crud_check.py --emit-cases ({path})",
        file=sys.stderr,
    )
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", choices=["gen", "civil"])
    parser.add_argument("--mapi-key", help="defaults to MIDAS_MAPI_KEY env var")
    parser.add_argument("--base-url", help="defaults to MIDAS_BASE_URL env var")
    parser.add_argument(
        "--tier",
        help="comma-separated tiers to run, in priority order: "
        + ", ".join(t.name for t in TIERS) + " (default: all)",
    )
    parser.add_argument(
        "--endpoints",
        help="comma-separated endpoint paths to run within the selected tier(s)",
    )
    parser.add_argument(
        "--save-as",
        help="an exact checkpoint path on the NX machine, extension included, "
        "used instead of deriving one under --save-dir. Naming either one "
        "satisfies the save requirement",
    )
    harness_save_path.add_arguments(parser)
    parser.add_argument(
        "--include-crashers",
        action="store_true",
        help="also run cases quarantined for hanging or killing MIDAS NX "
        "(currently /db/NMAS). Expect to restart the product and to redo the "
        "license-recovery steps afterwards.",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--out", help="path to write the report JSON (optional)")
    fixture_group = parser.add_mutually_exclusive_group()
    fixture_group.add_argument(
        "--emit-cases",
        action="store_true",
        help="write the language-neutral case fixture used by the npm live harness",
    )
    fixture_group.add_argument(
        "--check-cases",
        action="store_true",
        help="fail when the checked-in language-neutral case fixture has drifted",
    )
    parser.add_argument(
        "--cases-file",
        type=Path,
        default=LIVE_CASES_PATH,
        help=f"case fixture path (default: {LIVE_CASES_PATH})",
    )
    args = parser.parse_args()

    if args.emit_cases:
        _write_live_cases(args.cases_file)
        print(f"Wrote {args.cases_file}")
        return 0
    if args.check_cases:
        return 0 if _check_live_cases(args.cases_file) else 1
    if not _check_live_cases(args.cases_file):
        return 2
    if not args.product:
        parser.error("--product is required unless --emit-cases or --check-cases is used")
    tiers = TIERS
    if args.tier:
        wanted = [n.strip() for n in args.tier.split(",") if n.strip()]
        unknown = [n for n in wanted if n not in {t.name for t in TIERS}]
        if unknown:
            print(f"Unknown tier(s): {', '.join(unknown)}", file=sys.stderr)
            return 2
        tiers = [t for t in TIERS if t.name in wanted]
    endpoints = None
    if args.endpoints:
        endpoints = {item.strip() for item in args.endpoints.split(",") if item.strip()}
        # --tier refuses an unknown name before anything runs; this has to as
        # well. The filter is applied inside the tier loop, which is after
        # /doc/NEW has already discarded the caller's document - so a typo
        # would cost them that document and then test nothing.
        known: Dict[str, List[str]] = {}
        for known_tier in TIERS:
            for known_case in known_tier.cases():
                known.setdefault(known_case.resource.ENDPOINT, []).append(known_tier.name)
        selected = {t.name for t in tiers}
        for endpoint in sorted(endpoints):
            where = known.get(endpoint)
            if where is None:
                print(f"No live case for endpoint {endpoint}", file=sys.stderr)
                return 2
            if not selected.intersection(where):
                print(
                    f"{endpoint} has no case in the selected tier(s); it is in "
                    f"{', '.join(sorted(set(where)))}",
                    file=sys.stderr,
                )
                return 2

    # After the selection is validated and before the client exists. Late
    # enough that a typo in --tier or --endpoints is still reported as a typo
    # rather than as a missing save directory, and early enough that neither
    # refusal costs a connection. --emit-cases and --check-cases returned long
    # ago: they never reach a product, so they never call /doc/NEW.
    harness_save_path.require(parser, args, exact_path=args.save_as)
    checkpoint = args.save_as or (
        None if args.no_save_before
        else harness_save_path.checkpoint(args.save_dir, "midas-nx-crud", args.product)
    )

    client = MidasClient(
        mapi_key=args.mapi_key, base_url=args.base_url,
        product=args.product, timeout=args.timeout,
    )
    try:
        health = client.verify_connection()
    except MidasAPIError as exc:
        print(f"Could not reach the MIDAS NX Open API server: {exc}", file=sys.stderr)
        return 2
    if health.get("status") != "connected":
        print(f"Server reachable but not connected: {health}", file=sys.stderr)
        return 2

    if checkpoint:
        print(f"Saving the open document to {checkpoint} first...")
        doc.save_as(checkpoint, client=client)

    print("Creating a throwaway document and seeding a minimal model...")
    doc.new_project(client=client)
    try:
        _seed_model(client)
    except MidasAPIError as exc:
        print(f"Base seed failed, so nothing below it can be trusted: {exc}",
              file=sys.stderr)
        return 3

    product = client.product.value
    results: List[Dict[str, Any]] = []
    aborted = None
    for tier in tiers:
        if aborted:
            break
        cases = [c for c in tier.cases() if product in c.products]
        if endpoints is not None:
            cases = [c for c in cases if c.resource.ENDPOINT in endpoints]
        if not cases:
            continue
        print(f"\n[{tier.name}] {tier.title}")
        # Seed steps fail independently, and a case is only blocked by the
        # step it actually declared a need for.
        failed_seeds: Dict[str, str] = {}
        for step in (step for step in tier.seeds() if product in step.products):
            try:
                step.run(client)
            except MidasAPIError as exc:
                failed_seeds[step.name] = str(exc)[:160]
                print(f"  seed '{step.name}' failed: {failed_seeds[step.name]}")
        for case in cases:
            missing = [n for n in case.needs if n in failed_seeds]
            if case.crashes and not args.include_crashers:
                row = _stub_row(case, SKIPPED, case.crashes)
            elif missing:
                row = _stub_row(case, BLOCKED,
                                f"seed '{missing[0]}': {failed_seeds[missing[0]]}")
            else:
                row = _run_case(case, client)
            results.append(row)
            marks = " ".join(
                f"{name}={'ok' if step.get('ok') else 'FAIL'}"
                for name, step in row["steps"].items()
            )
            print(f"  {_mark(row):8}{row['endpoint']:12} {marks}")
            if _session_lost(row):
                aborted = (f"the product stopped answering at {row['endpoint']} — "
                           f"MIDAS NX is hung or gone, so nothing after this "
                           f"point was tested")
                print(f"\n!! ABORTED: {aborted}")
                break

    by_class = {k: [r for r in results if r["classification"] == k]
                for k in (OK, REGRESSION, UNVERIFIED, BLOCKED, SKIPPED)}
    report = {
        "product": product,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "connection": {k: health.get(k) for k in ("user", "program", "connectionID")},
        "tiers": [t.name for t in tiers],
        "aborted": aborted,
        "cases": len(results),
        "passed": len(by_class[OK]),
        "regressions": len(by_class[REGRESSION]),
        "unverified_failures": len(by_class[UNVERIFIED]),
        "blocked": len(by_class[BLOCKED]),
        "skipped": len(by_class[SKIPPED]),
        "results": results,
    }

    print()
    print(f"{len(by_class[OK])}/{len(results)} resources completed a full round trip.")
    if by_class[REGRESSION]:
        print(f"  {len(by_class[REGRESSION])} REGRESSION - a case that passed live "
              f"before now fails; treat as an SDK defect:")
        for r in by_class[REGRESSION]:
            print(f"      {r['endpoint']}")
    if by_class[UNVERIFIED]:
        print(f"  {len(by_class[UNVERIFIED])} unverified failure(s) - never passed "
              f"live; triage the fixture payload before blaming the SDK:")
        for r in by_class[UNVERIFIED]:
            print(f"      {r['endpoint']}")
    if by_class[BLOCKED]:
        print(f"  {len(by_class[BLOCKED])} blocked by a failed seed (fixture problem):")
        for r in by_class[BLOCKED]:
            print(f"      {r['endpoint']}")
    if by_class[SKIPPED]:
        print(f"  {len(by_class[SKIPPED])} quarantined, not run "
              f"(pass --include-crashers to run anyway):")
        for r in by_class[SKIPPED]:
            print(f"      {r['endpoint']} - {r['blocked_by']}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f"Report written to {args.out}")

    # Every case leaves a deliberately-created model behind.  Save it to a
    # distinct C:/temp checkpoint before making a new document; otherwise the
    # next /doc/NEW can display NX's modal "save changes?" prompt even though
    # the caller saved the document that was open before this run.
    if checkpoint:
        final_checkpoint = _final_checkpoint_path(checkpoint)
        try:
            print(f"Saving the throwaway model to {final_checkpoint} before cleanup...")
            doc.save_as(final_checkpoint, client=client)
            doc.new_project(client=client)
            nodes = Node.items(client=client)
            elements = Element.items(client=client)
            if nodes or elements:
                print("/doc/NEW did not leave an empty NODE/ELEM scratch document; "
                      "refusing to report the run as safely cleaned up.", file=sys.stderr)
                return 2
            print("Saved throwaway model and restored an empty scratch document.")
        except MidasAPIError as exc:
            print(f"Could not save and clean up the throwaway model: {exc}", file=sys.stderr)
            return 2

    if by_class[REGRESSION]:
        return 1
    if by_class[UNVERIFIED] or by_class[BLOCKED]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

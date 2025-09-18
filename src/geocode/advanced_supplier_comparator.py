#!/usr/bin/env python3
"""
Advanced Supplier Discovery Comparator with Improved Cross-Provider Deduplication
Preserves full raw data from each provider and uses sophisticated matching algorithms.
"""
import asyncio
import time
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
import difflib
import re
from dataclasses import dataclass, asdict
from geopy.distance import geodesic

# Your existing components
from src.core.config import settings
from src.geocode.providers import (
    NominatimProvider, LocationIQProvider, OpenCageProvider,
    HereProvider, MapboxProvider, GoogleProvider, GeocodeError
)
from src.discovery.discovery_filter_and_deduplication_async_caching_log_sortAndDedupFirst import find_suppliers

@dataclass
class ProviderSupplierData:
    """Raw supplier data from a specific provider."""
    name: str
    lat: float
    lon: float
    distance_miles: float
    source: str = "overpass"
    confidence: float = 0.0
    address: str = ""
    street: str = ""
    postcode: str = ""
    city: str = ""
    country: str = ""
    raw_osm_tags: Dict = None
    reverse_geocode_raw: Dict = None
    
    def __post_init__(self):
        if self.raw_osm_tags is None:
            self.raw_osm_tags = {}
        if self.reverse_geocode_raw is None:
            self.reverse_geocode_raw = {}

@dataclass 
class UnifiedSupplier:
    """Unified supplier entry found by multiple providers."""
    canonical_name: str
    canonical_lat: float
    canonical_lon: float
    distance_miles: float
    found_by_providers: Dict[str, ProviderSupplierData]
    consensus_level: int  # How many providers found this
    coordinate_variance_meters: float
    name_variations: List[str]
    best_address: str
    confidence_scores: Dict[str, float]
    
class AdvancedSupplierMatcher:
    """Advanced matching algorithms for cross-provider supplier deduplication."""
    
    def __init__(self):
        self.distance_threshold_meters = 150.0  # Increased for large facilities
        self.name_similarity_threshold = 0.7    # Fuzzy string matching
        
    def normalize_company_name(self, name: str) -> str:
        """Normalize company names for better matching."""
        if not name or name.lower() in ["unknown", "", "n/a"]:
            return "unknown"
        
        # Remove common suffixes and legal entities
        suffixes = [
            r'\s+(ltd|limited|plc|inc|incorporated|corp|corporation|llc|gmbh)\.?$',
            r'\s+(uk|usa|us|europe|international)\.?$',
            r'\s+\(.*\)$',  # Remove parenthetical info
        ]
        
        normalized = name.lower().strip()
        for suffix_pattern in suffixes:
            normalized = re.sub(suffix_pattern, '', normalized, flags=re.IGNORECASE)
        
        # Normalize whitespace and punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two company names."""
        if not name1 or not name2:
            return 0.0
            
        norm1 = self.normalize_company_name(name1)
        norm2 = self.normalize_company_name(name2)
        
        if norm1 == "unknown" or norm2 == "unknown":
            return 0.8 if norm1 == norm2 else 0.3
        
        # Use difflib for string similarity
        similarity = difflib.SequenceMatcher(None, norm1, norm2).ratio()
        
        # Boost similarity for common abbreviations
        if self._check_abbreviation_match(norm1, norm2):
            similarity = max(similarity, 0.85)
            
        return similarity
    
    def _check_abbreviation_match(self, name1: str, name2: str) -> bool:
        """Check if names might be abbreviation variants."""
        # Common aerospace/industrial abbreviations
        abbreviations = [
            ("bae systems", "bae"),
            ("rolls royce", "rr"),
            ("general electric", "ge"),
            ("leonardo", "leonardo helicopters"),
            ("airbus", "airbus uk"),
        ]
        
        for full, abbrev in abbreviations:
            if (full in name1 and abbrev in name2) or (full in name2 and abbrev in name1):
                return True
        return False
    
    def match_suppliers_across_providers(self, provider_results: Dict[str, List[Dict]]) -> List[UnifiedSupplier]:
        """Advanced cross-provider supplier matching and deduplication."""
        
        # Convert to structured data
        all_suppliers = []
        for provider_name, suppliers in provider_results.items():
            for supplier in suppliers:
                supplier_data = ProviderSupplierData(
                    name=supplier.get("name", "Unknown"),
                    lat=float(supplier.get("lat", 0)),
                    lon=float(supplier.get("lon", 0)),
                    distance_miles=float(supplier.get("distance_miles", 0)),
                    source=supplier.get("source", "overpass"),
                    confidence=float(supplier.get("confidence", 0)),
                    address=supplier.get("address", ""),
                    street=supplier.get("street", ""),
                    postcode=supplier.get("postcode", ""),
                    city=supplier.get("city", ""),
                    country=supplier.get("country", ""),
                    raw_osm_tags=supplier.get("raw_osm_tags", {}),
                    reverse_geocode_raw=supplier.get("reverse_geocode_raw", {})
                )
                all_suppliers.append((provider_name, supplier_data))
        
        # Group suppliers using advanced matching
        unified_groups = []
        processed = set()
        
        for i, (provider1, supplier1) in enumerate(all_suppliers):
            if i in processed:
                continue
                
            # Start new unified group
            group = {provider1: supplier1}
            processed.add(i)
            
            # Find matches in remaining suppliers
            for j, (provider2, supplier2) in enumerate(all_suppliers[i+1:], i+1):
                if j in processed:
                    continue
                
                if self._suppliers_match(supplier1, supplier2):
                    group[provider2] = supplier2
                    processed.add(j)
            
            unified_groups.append(group)
        
        # Convert groups to UnifiedSupplier objects
        unified_suppliers = []
        for group in unified_groups:
            unified = self._create_unified_supplier(group)
            unified_suppliers.append(unified)
        
        return sorted(unified_suppliers, key=lambda x: x.distance_miles)
    
    def _suppliers_match(self, s1: ProviderSupplierData, s2: ProviderSupplierData) -> bool:
        """Check if two suppliers from different providers are the same entity."""
        
        # Distance check - must be within threshold
        distance_m = geodesic((s1.lat, s1.lon), (s2.lat, s2.lon)).meters
        if distance_m > self.distance_threshold_meters:
            return False
        
        # Name similarity check
        name_similarity = self.calculate_name_similarity(s1.name, s2.name)
        if name_similarity >= self.name_similarity_threshold:
            return True
        
        # Special case: both unknown but very close
        if (s1.name.lower() in ["unknown", ""] and s2.name.lower() in ["unknown", ""] and 
            distance_m < 25.0):
            return True
        
        return False
    
    def _create_unified_supplier(self, provider_group: Dict[str, ProviderSupplierData]) -> UnifiedSupplier:
        """Create unified supplier from group of provider matches."""
        
        # Choose canonical name (prefer named over "Unknown")
        names = [s.name for s in provider_group.values() if s.name.lower() not in ["unknown", ""]]
        canonical_name = names[0] if names else "Unknown"
        
        # Calculate centroid coordinates
        lats = [s.lat for s in provider_group.values()]
        lons = [s.lon for s in provider_group.values()]
        canonical_lat = sum(lats) / len(lats)
        canonical_lon = sum(lons) / len(lons)
        
        # Calculate coordinate variance
        distances = [geodesic((canonical_lat, canonical_lon), (s.lat, s.lon)).meters 
                    for s in provider_group.values()]
        coordinate_variance_meters = max(distances) if distances else 0.0
        
        # Average distance
        distance_miles = sum(s.distance_miles for s in provider_group.values()) / len(provider_group)
        
        # Collect all name variations
        name_variations = list(set(s.name for s in provider_group.values() if s.name.lower() != "unknown"))
        
        # Choose best address (longest non-empty one)
        addresses = [s.address for s in provider_group.values() if s.address.strip()]
        best_address = max(addresses, key=len) if addresses else ""
        
        # Collect confidence scores
        confidence_scores = {provider: supplier.confidence 
                           for provider, supplier in provider_group.items()}
        
        return UnifiedSupplier(
            canonical_name=canonical_name,
            canonical_lat=canonical_lat,
            canonical_lon=canonical_lon,
            distance_miles=round(distance_miles, 2),
            found_by_providers=provider_group,
            consensus_level=len(provider_group),
            coordinate_variance_meters=round(coordinate_variance_meters, 1),
            name_variations=name_variations,
            best_address=best_address,
            confidence_scores=confidence_scores
        )

class AdvancedSupplierDiscoveryComparator:
    """Advanced comparison with full raw data preservation."""
    
    def __init__(self, address: str, radius: int, reference_coords: Tuple[float, float] = None):
        self.address = address
        self.radius = radius
        self.reference_coords = reference_coords
        self.provider_results = {}
        self.unified_suppliers = []
        self.analysis = {}
        self.matcher = AdvancedSupplierMatcher()
        
    def _init_providers(self) -> Dict[str, object]:
        """Initialize available geocoding providers."""
        providers = {}
        provider_classes = [
            ("Google", GoogleProvider),
            ("HERE", HereProvider), 
            ("Mapbox", MapboxProvider),
            ("LocationIQ", LocationIQProvider),
            ("OpenCage", OpenCageProvider),
            ("Nominatim", NominatimProvider),
        ]
        
        print("🔍 Initializing Geocoding Providers:")
        for name, cls in provider_classes:
            try:
                provider = cls()
                providers[name] = provider
                print(f"  ✅ {name:12} Ready")
            except Exception as e:
                print(f"  ❌ {name:12} Failed: {str(e)[:50]}...")
        
        return providers
    
    async def run_discovery_with_provider(self, provider_name: str, provider) -> Dict:
        """Run discovery with full raw data capture."""
        print(f"🚀 Running discovery with {provider_name}...")
        start_time = time.time()
        
        try:
            # Geocode
            geocode_start = time.time()
            lat, lon = await provider.geocode(self.address)
            geocode_time = time.time() - geocode_start
            
            accuracy_meters = None
            if self.reference_coords:
                accuracy_meters = geodesic(self.reference_coords, (lat, lon)).meters
            
            print(f"  📍 {provider_name} → {lat:.5f}, {lon:.5f} ({geocode_time:.1f}s)")
            if accuracy_meters:
                print(f"  🎯 Accuracy: {accuracy_meters:.1f}m from reference")
            
            # Find suppliers with full raw data
            discovery_start = time.time()
            suppliers = await find_suppliers(
                lat, lon, self.radius,
                deduplicate=True,  # Use your existing dedup within provider
                reverse_geocode=True,
                cache=True
            )
            discovery_time = time.time() - discovery_start
            
            # Enhance with additional metadata we'll need for comparison
            for supplier in suppliers:
                supplier['provider'] = provider_name
                supplier['geocode_accuracy'] = accuracy_meters
                supplier['geocoded_center'] = (lat, lon)
            
            total_time = time.time() - start_time
            
            result = {
                'provider': provider_name,
                'success': True,
                'geocoded_center': (lat, lon),
                'accuracy_meters': round(accuracy_meters, 1) if accuracy_meters else None,
                'supplier_count': len(suppliers),
                'suppliers': suppliers,
                'timing': {
                    'geocoding_seconds': round(geocode_time, 1),
                    'discovery_seconds': round(discovery_time, 1),
                    'total_seconds': round(total_time, 1)
                },
                'data_quality': self._assess_data_quality(suppliers)
            }
            
            print(f"  ✅ Found {len(suppliers)} suppliers ({total_time:.1f}s total)")
            print(f"  📊 Data quality: {result['data_quality']['completeness_percentage']:.1f}%\n")
            
            return result
            
        except Exception as e:
            error_time = time.time() - start_time
            print(f"  ❌ {provider_name} failed: {str(e)}\n")
            return {
                'provider': provider_name,
                'success': False,
                'error': str(e),
                'timing': {'total_seconds': round(error_time, 1)}
            }
    
    def _assess_data_quality(self, suppliers: List[Dict]) -> Dict:
        """Assess data completeness and quality."""
        if not suppliers:
            return {'completeness_percentage': 0, 'assessment': 'No data'}
        
        fields_to_check = ['name', 'address', 'street', 'postcode', 'city']
        total_possible = len(suppliers) * len(fields_to_check)
        filled_count = 0
        
        for supplier in suppliers:
            for field in fields_to_check:
                value = supplier.get(field, '')
                if value and str(value).strip() and str(value).lower() != 'unknown':
                    filled_count += 1
        
        completeness_percentage = (filled_count / total_possible) * 100
        
        # Additional quality metrics
        named_suppliers = sum(1 for s in suppliers if s.get('name', '').strip() and s.get('name', '').lower() != 'unknown')
        with_addresses = sum(1 for s in suppliers if s.get('address', '').strip())
        with_postcodes = sum(1 for s in suppliers if s.get('postcode', '').strip())
        
        return {
            'completeness_percentage': round(completeness_percentage, 1),
            'named_suppliers': named_suppliers,
            'suppliers_with_addresses': with_addresses,
            'suppliers_with_postcodes': with_postcodes,
            'assessment': self._quality_assessment(completeness_percentage)
        }
    
    def _quality_assessment(self, percentage: float) -> str:
        """Qualitative assessment of data quality."""
        if percentage >= 80:
            return "Excellent"
        elif percentage >= 60:
            return "Good" 
        elif percentage >= 40:
            return "Fair"
        elif percentage >= 20:
            return "Poor"
        else:
            return "Very Poor"
    
    async def run_full_comparison(self):
        """Run comprehensive cross-provider comparison."""
        providers = self._init_providers()
        
        if not providers:
            print("❌ No providers available.")
            return
        
        print(f"🎯 Target: '{self.address}' within {self.radius} miles")
        if self.reference_coords:
            print(f"📍 Reference: {self.reference_coords[0]:.5f}, {self.reference_coords[1]:.5f}")
        print("=" * 80)
        
        # Run discovery with each provider
        tasks = [
            self.run_discovery_with_provider(name, provider)
            for name, provider in providers.items()
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Store successful results
        successful_results = [r for r in results if r.get('success')]
        self.provider_results = {r['provider']: r['suppliers'] for r in successful_results}
        
        if not successful_results:
            print("❌ No providers succeeded.")
            return
        
        print(f"✅ Discovery complete: {len(successful_results)}/{len(providers)} providers succeeded")
        
        # Advanced cross-provider matching and deduplication
        print("\n🧬 Performing advanced cross-provider supplier matching...")
        self.unified_suppliers = self.matcher.match_suppliers_across_providers(self.provider_results)
        
        # Generate comprehensive analysis
        self.analysis = self._generate_comprehensive_analysis(successful_results)
        
        print(f"📊 Analysis complete: {len(self.unified_suppliers)} unique suppliers identified")
    
    def _generate_comprehensive_analysis(self, results: List[Dict]) -> Dict:
        """Generate detailed cross-provider analysis."""
        analysis = {
            'summary': {
                'query_address': self.address,
                'search_radius_miles': self.radius,
                'providers_tested': len(results),
                'successful_providers': len(results),
                'total_unified_suppliers': len(self.unified_suppliers),
                'reference_coords': self.reference_coords
            }
        }
        
        # Provider-level statistics
        provider_stats = {}
        for result in results:
            provider_stats[result['provider']] = {
                'supplier_count': result['supplier_count'],
                'accuracy_meters': result.get('accuracy_meters'),
                'total_seconds': result['timing']['total_seconds'],
                'data_quality': result['data_quality']
            }
        
        analysis['provider_statistics'] = provider_stats
        
        # Consensus analysis
        consensus_levels = defaultdict(int)
        for supplier in self.unified_suppliers:
            consensus_levels[supplier.consensus_level] += 1
        
        analysis['consensus_analysis'] = {
            'consensus_distribution': dict(consensus_levels),
            'high_consensus_suppliers': len([s for s in self.unified_suppliers if s.consensus_level >= len(results) * 0.75]),
            'unique_discoveries': len([s for s in self.unified_suppliers if s.consensus_level == 1]),
            'average_consensus_level': sum(s.consensus_level for s in self.unified_suppliers) / len(self.unified_suppliers) if self.unified_suppliers else 0
        }
        
        # Name variation analysis
        name_variations = []
        for supplier in self.unified_suppliers:
            if len(supplier.name_variations) > 1:
                name_variations.append({
                    'canonical_name': supplier.canonical_name,
                    'variations': supplier.name_variations,
                    'providers': list(supplier.found_by_providers.keys())
                })
        
        analysis['name_variation_analysis'] = {
            'suppliers_with_name_variations': len(name_variations),
            'examples': name_variations[:10]  # Top 10 examples
        }
        
        # Coordinate precision analysis
        coordinate_variances = [s.coordinate_variance_meters for s in self.unified_suppliers if s.coordinate_variance_meters > 0]
        if coordinate_variances:
            analysis['coordinate_precision'] = {
                'average_variance_meters': round(sum(coordinate_variances) / len(coordinate_variances), 1),
                'max_variance_meters': max(coordinate_variances),
                'suppliers_with_variance': len(coordinate_variances)
            }
        
        return analysis
    
    def generate_detailed_report(self) -> str:
        """Generate comprehensive comparison report with full raw data insights."""
        if not self.analysis:
            return "No analysis data available."
        
        report = f"""
# Advanced Geocoding Provider Comparison Report
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Query Summary
- **Target:** {self.analysis['summary']['query_address']}
- **Search Radius:** {self.analysis['summary']['search_radius_miles']} miles  
- **Providers Tested:** {self.analysis['summary']['providers_tested']}
- **Total Unique Suppliers:** {self.analysis['summary']['total_unified_suppliers']}
"""
        
        if self.reference_coords:
            report += f"- **Reference Coordinates:** {self.reference_coords[0]:.5f}, {self.reference_coords[1]:.5f}\n"
        
        # Provider Performance Comparison
        report += "\n## Provider Performance Comparison\n\n"
        report += "| Provider | Suppliers | Accuracy (m) | Time (s) | Data Quality | Unique Finds |\n"
        report += "|----------|-----------|--------------|----------|--------------|-------------|\n"
        
        for provider, stats in self.analysis['provider_statistics'].items():
            accuracy = f"{stats.get('accuracy_meters', 0):.1f}" if stats.get('accuracy_meters') else "N/A"
            unique_count = len([s for s in self.unified_suppliers if provider in s.found_by_providers and s.consensus_level == 1])
            
            report += f"| {provider:8} | {stats['supplier_count']:8} | {accuracy:10} | {stats['total_seconds']:6.1f} | {stats['data_quality']['assessment']:11} | {unique_count:11} |\n"
        
        # Cross-Provider Consensus Analysis
        report += f"\n## Cross-Provider Consensus Analysis\n"
        
        if self.analysis.get('consensus_analysis'):
            ca = self.analysis['consensus_analysis']
            report += f"**High consensus suppliers:** {ca['high_consensus_suppliers']} (found by ≥75% of providers)\n"
            report += f"**Unique discoveries:** {ca['unique_discoveries']} (found by only 1 provider)\n"
            report += f"**Average consensus level:** {ca['average_consensus_level']:.1f} providers per supplier\n\n"
            
            report += "**Consensus Distribution:**\n"
            for level, count in sorted(ca['consensus_distribution'].items(), reverse=True):
                report += f"  - Found by {level} provider(s): {count} suppliers\n"
        
        # Name Variation Analysis
        if self.analysis.get('name_variation_analysis'):
            nva = self.analysis['name_variation_analysis']
            report += f"\n## Name Variation Analysis\n"
            report += f"**Suppliers with name variations:** {nva['suppliers_with_name_variations']}\n\n"
            
            if nva['examples']:
                report += "**Examples of name variations:**\n"
                for example in nva['examples'][:5]:
                    report += f"- **{example['canonical_name']}**\n"
                    for variation in example['variations']:
                        report += f"  - {variation}\n"
                    report += f"  - Found by: {', '.join(example['providers'])}\n\n"
        
        # Coordinate Precision Analysis
        if self.analysis.get('coordinate_precision'):
            cp = self.analysis['coordinate_precision']
            report += f"## Coordinate Precision Analysis\n"
            report += f"**Average coordinate variance:** {cp['average_variance_meters']} meters\n"
            report += f"**Maximum variance:** {cp['max_variance_meters']} meters\n"
            report += f"**Suppliers with coordinate variance:** {cp['suppliers_with_variance']}\n\n"
        
        # Detailed Supplier Examples
        report += "## Detailed Supplier Examples\n\n"
        
        # High consensus example
        high_consensus = [s for s in self.unified_suppliers if s.consensus_level >= 4][:3]
        if high_consensus:
            report += "### High Consensus Suppliers (Found by Multiple Providers)\n"
            for supplier in high_consensus:
                report += f"**{supplier.canonical_name}**\n"
                report += f"- Found by {supplier.consensus_level} providers: {', '.join(supplier.found_by_providers.keys())}\n"
                report += f"- Coordinates: {supplier.canonical_lat:.5f}, {supplier.canonical_lon:.5f}\n"
                report += f"- Coordinate variance: {supplier.coordinate_variance_meters}m\n"
                if len(supplier.name_variations) > 1:
                    report += f"- Name variations: {', '.join(supplier.name_variations)}\n"
                report += f"- Best address: {supplier.best_address}\n\n"
        
        # Unique discoveries example
        unique_discoveries = [s for s in self.unified_suppliers if s.consensus_level == 1][:3]
        if unique_discoveries:
            report += "### Unique Discoveries (Found by Single Provider Only)\n"
            for supplier in unique_discoveries:
                provider_name = list(supplier.found_by_providers.keys())[0]
                report += f"**{supplier.canonical_name}** (found only by {provider_name})\n"
                report += f"- Coordinates: {supplier.canonical_lat:.5f}, {supplier.canonical_lon:.5f}\n"
                report += f"- Distance: {supplier.distance_miles} miles\n"
                report += f"- Address: {supplier.best_address}\n\n"
        
        # Professional Recommendations
        report += "## Professional Assessment\n\n"
        
        # Find best provider
        if self.analysis['provider_statistics']:
            best_provider = None
            best_score = 0
            
            for provider, stats in self.analysis['provider_statistics'].items():
                # Score based on supplier count, data quality, and speed
                score = (stats['supplier_count'] * 0.4 + 
                        (100 - stats.get('accuracy_meters', 100)) * 0.3 +
                        max(0, 600 - stats['total_seconds']) * 0.3)
                
                if score > best_score:
                    best_score = score
                    best_provider = provider
            
            if best_provider:
                report += f"**Recommended Primary Provider:** {best_provider}\n"
                report += "  - Best combination of discovery coverage, accuracy, and performance\n\n"
        
        # Impact assessment
        unique_count = self.analysis['consensus_analysis']['unique_discoveries']
        total_count = self.analysis['summary']['total_unified_suppliers']
        unique_percentage = (unique_count / total_count * 100) if total_count else 0
        
        if unique_percentage < 5:
            impact = "**Impact Assessment:** MINIMAL - Provider choice has negligible effect on supplier discovery."
        elif unique_percentage < 15:
            impact = "**Impact Assessment:** LOW - Small differences in supplier discovery between providers."
        elif unique_percentage < 30:
            impact = "**Impact Assessment:** MODERATE - Notable differences in supplier discovery between providers."
        else:
            impact = "**Impact Assessment:** HIGH - Significant differences in supplier discovery between providers."
        
        report += impact + "\n\n"
        
        # Data quality insights
        report += "**Key Data Quality Insights:**\n"
        report += f"- Name standardization needed: {len([s for s in self.unified_suppliers if len(s.name_variations) > 1])} suppliers have name variations\n"
        report += f"- Coordinate precision: Average {self.analysis.get('coordinate_precision', {}).get('average_variance_meters', 0)}m variance between providers\n"
        report += f"- Provider reliability: {len([p for p, s in self.analysis['provider_statistics'].items() if s['data_quality']['assessment'] in ['Good', 'Excellent']])}/{len(self.analysis['provider_statistics'])} providers deliver good quality data\n"
        
        return report
    
    def save_comprehensive_results(self, output_dir: str = "output"):
        """Save all results including raw provider data and unified suppliers."""
        Path(output_dir).mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Save unified suppliers with full cross-provider data
        unified_file = Path(output_dir) / f"unified_suppliers_{timestamp}.json"
        unified_data = []
        for supplier in self.unified_suppliers:
            supplier_dict = asdict(supplier)
            # Convert ProviderSupplierData objects to dicts
            supplier_dict['found_by_providers'] = {
                provider: asdict(data) for provider, data in supplier.found_by_providers.items()
            }
            unified_data.append(supplier_dict)
        
        with open(unified_file, "w") as f:
            json.dump(unified_data, f, indent=2, default=str)
        
        # Save raw provider results
        raw_file = Path(output_dir) / f"raw_provider_results_{timestamp}.json"
        with open(raw_file, "w") as f:
            json.dump(self.provider_results, f, indent=2, default=str)
        
        # Save analysis
        analysis_file = Path(output_dir) / f"cross_provider_analysis_{timestamp}.json"
        with open(analysis_file, "w") as f:
            json.dump(self.analysis, f, indent=2, default=str)
        
        # Save detailed report
        report = self.generate_detailed_report()
        report_file = Path(output_dir) / f"advanced_comparison_report_{timestamp}.txt"
        with open(report_file, "w") as f:
            f.write(report)
        
        print(f"\n💾 Comprehensive results saved:")
        print(f"📊 Unified suppliers: {unified_file.name}")
        print(f"🗃️  Raw provider data: {raw_file.name}")
        print(f"📈 Analysis data: {analysis_file.name}")
        print(f"📋 Report: {report_file.name}")
        
        return str(report_file)

async def main():
    """Main advanced comparison workflow."""
    print("🚀 Advanced Supplier Discovery Cross-Provider Comparison")
    print("=" * 80)
    
    # Configuration
    ADDRESS = "Airbus, Filton, Bristol, UK"
    RADIUS = 20  # miles
    REFERENCE_COORDS = (51.5088, -2.5783)  # Known Airbus Filton coordinates
    
    print(f"📍 Target: {ADDRESS}")
    print(f"📏 Radius: {RADIUS} miles")
    print(f"🎯 Reference: {REFERENCE_COORDS[0]:.5f}, {REFERENCE_COORDS[1]:.5f}")
    print("🧬 Advanced cross-provider matching enabled")
    print()
    
    # Run advanced comparison
    comparator = AdvancedSupplierDiscoveryComparator(ADDRESS, RADIUS, REFERENCE_COORDS)
    
    total_start = time.time()
    await comparator.run_full_comparison()
    total_time = time.time() - total_start
    
    print(f"⏱️  Total analysis time: {total_time/60:.1f} minutes")
    
    # Generate and display detailed report
    report = comparator.generate_detailed_report()
    print("\n" + "=" * 80)
    print("ADVANCED COMPARISON REPORT")
    print("=" * 80)
    print(report)
    
    # Save comprehensive results
    report_file = comparator.save_comprehensive_results()
    print(f"\n📋 Full report saved: {report_file}")

if __name__ == "__main__":
    print("Advanced Supplier Discovery Cross-Provider Comparison")
    print("Features:")
    print("- Advanced fuzzy name matching across providers")
    print("- Full raw data preservation from each provider")
    print("- Sophisticated deduplication with coordinate clustering")
    print("- Comprehensive cross-provider consensus analysis")
    print("- Expected runtime: 15-45 minutes")
    print()
    
    response = input("Continue with advanced comparison? (y/N): ").lower().strip()
    if response != 'y':
        print("Comparison cancelled.")
        exit(0)
    
    asyncio.run(main())
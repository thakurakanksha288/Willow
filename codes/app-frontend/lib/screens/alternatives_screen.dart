import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../model/scan_model.dart';
import '../services/ingredient_scanner_service.dart';
import '../theme/app_theme.dart';

class AlternativesScreen extends StatefulWidget {
  final ProductAnalysis originalProduct;

  const AlternativesScreen({
    super.key,
    required this.originalProduct,
  });

  @override
  State<AlternativesScreen> createState() => _AlternativesScreenState();
}

class _AlternativesScreenState extends State<AlternativesScreen> {
  final _scanner = IngredientScannerService();

  AiAlternativesResult? _aiResult;
  List<AlternativeSwap> _alternatives = [];
  bool _isLoading = true;
  String _selectedFilter = 'All'; // 'All', 'Packaged Brand', 'Whole Food Alternative'

  @override
  void initState() {
    super.initState();
    _alternatives = widget.originalProduct.alternatives;
    _loadAiAlternatives();
  }

  Future<void> _loadAiAlternatives() async {
    final p = widget.originalProduct;
    final ingredients = [
      ...p.flagged.map((f) => f.rawToken.isNotEmpty ? f.rawToken : f.canonical),
      ...p.clean.map((c) => c.rawToken.isNotEmpty ? c.rawToken : c.canonical),
      ...p.unknown,
    ].where((s) => s.isNotEmpty).toList();

    final flaggedNames = p.flagged.map((f) => f.canonical).toList();

    try {
      final res = await _scanner.getAiAlternatives(
        productName: p.productName,
        category: p.category,
        ingredients: ingredients,
        currentScore: p.displayScore,
        flaggedIngredients: flaggedNames,
      );

      if (mounted) {
        setState(() {
          _isLoading = false;
          if (res != null && res.alternatives.isNotEmpty) {
            _aiResult = res;
            _alternatives = res.alternatives;
          }
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  List<AlternativeSwap> get _filteredAlternatives {
    if (_selectedFilter == 'All') return _alternatives;
    return _alternatives.where((a) {
      final st = a.swapType?.toLowerCase() ?? '';
      if (_selectedFilter == 'Packaged Brand') {
        return st.contains('packaged') || st.contains('brand') || st.contains('clean');
      }
      if (_selectedFilter == 'Whole Food Alternative') {
        return st.contains('whole') || st.contains('food') || st.contains('kitchen');
      }
      return true;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final originalScore = widget.originalProduct.displayScore;
    final displayAlts = _filteredAlternatives;

    return Scaffold(
      backgroundColor: AppTheme.bgLight,
      body: Stack(
        children: [
          // ── Top Ambient Gradient Banner (Figma #2:2064) ──────────
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            height: 280,
            child: Container(
              decoration: const BoxDecoration(
                gradient: AppTheme.alternativesTopGradient,
              ),
            ),
          ),

          SafeArea(
            child: Column(
              children: [
                // ── Page Header (Figma #2:2071) ───────────────────────
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      // Back Button
                      GestureDetector(
                        onTap: () => Navigator.pop(context),
                        child: Container(
                          width: 36,
                          height: 36,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.25),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.arrow_back_rounded,
                            color: AppTheme.textHeading,
                            size: 20,
                          ),
                        ),
                      ),
                      Row(
                        children: [
                          Text(
                            'Better-rated swaps',
                            style: GoogleFonts.inter(
                              fontSize: 17,
                              fontWeight: FontWeight.w700,
                              color: AppTheme.textHeading,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.3),
                              borderRadius: BorderRadius.circular(100),
                            ),
                            child: Row(
                              children: [
                                const Icon(Icons.auto_awesome_rounded, size: 11, color: AppTheme.textHeading),
                                const SizedBox(width: 4),
                                Text(
                                  _aiResult?.isAiPowered == true ? 'Gemini AI' : 'AI Mode',
                                  style: GoogleFonts.inter(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w700,
                                    color: AppTheme.textHeading,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      GestureDetector(
                        onTap: () {
                          setState(() {
                            _isLoading = true;
                          });
                          _loadAiAlternatives();
                        },
                        child: Container(
                          width: 36,
                          height: 36,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.25),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.refresh_rounded,
                            color: AppTheme.textHeading,
                            size: 18,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                Expanded(
                  child: SingleChildScrollView(
                    physics: const BouncingScrollPhysics(),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        // ── Hero Intro (Figma #12:68) ─────────────────────────
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'A better choice.',
                                style: GoogleFonts.inter(
                                  fontSize: 30,
                                  fontWeight: FontWeight.w700,
                                  height: 1.15,
                                  color: AppTheme.textHeading,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                _aiResult != null && _aiResult!.summary.isNotEmpty
                                    ? _aiResult!.summary
                                    : 'Healthier alternatives curated to replace harmful additives.',
                                style: GoogleFonts.inter(
                                  fontSize: 13,
                                  color: AppTheme.textHeading.withValues(alpha: 0.9),
                                  height: 1.4,
                                ),
                              ),
                            ],
                          ),
                        ),

                        // ── Main Content Container (Figma #12:69) ─────────────
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
                          decoration: const BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.only(
                              topLeft: Radius.circular(28),
                              topRight: Radius.circular(28),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              // ── Original Product Comparison Bar (Figma #2:2079) ─
                              Container(
                                padding: const EdgeInsets.all(14),
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  borderRadius: BorderRadius.circular(18),
                                  border: Border.all(color: AppTheme.borderLight),
                                  boxShadow: [
                                    BoxShadow(
                                      color: AppTheme.primaryPurple.withValues(alpha: 0.1),
                                      blurRadius: 12,
                                      offset: const Offset(0, 4),
                                    ),
                                  ],
                                ),
                                child: Row(
                                  children: [
                                    Container(
                                      width: 40,
                                      height: 48,
                                      alignment: Alignment.center,
                                      decoration: BoxDecoration(
                                        color: AppTheme.primaryPurpleSoft,
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: const Icon(
                                        Icons.inventory_2_outlined,
                                        color: AppTheme.primaryPurple,
                                        size: 24,
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            'SWAPPING FROM',
                                            style: GoogleFonts.inter(
                                              fontSize: 10,
                                              fontWeight: FontWeight.w600,
                                              color: AppTheme.textMuted,
                                              letterSpacing: 0.5,
                                            ),
                                          ),
                                          const SizedBox(height: 2),
                                          Text(
                                            widget.originalProduct.productName,
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: GoogleFonts.inter(
                                              fontSize: 14,
                                              fontWeight: FontWeight.w600,
                                              color: AppTheme.textPrimary,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 10,
                                        vertical: 5,
                                      ),
                                      decoration: BoxDecoration(
                                        gradient: AppTheme.scoreGradient(originalScore),
                                        borderRadius: BorderRadius.circular(100),
                                      ),
                                      child: Text(
                                        '$originalScore/100',
                                        style: GoogleFonts.inter(
                                          fontSize: 12,
                                          fontWeight: FontWeight.w700,
                                          color: Colors.white,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 18),

                              // ── Category Filter Tabs ─────────────────────────
                              SingleChildScrollView(
                                scrollDirection: Axis.horizontal,
                                physics: const BouncingScrollPhysics(),
                                child: Row(
                                  children: [
                                    _buildFilterChip('All', 'All Swaps'),
                                    const SizedBox(width: 8),
                                    _buildFilterChip('Packaged Brand', 'Packaged Brands'),
                                    const SizedBox(width: 8),
                                    _buildFilterChip('Whole Food Alternative', 'Whole Foods & Kitchen'),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 18),

                              // ── Loading indicator while Gemini is analyzing ──
                              if (_isLoading) ...[
                                Container(
                                  padding: const EdgeInsets.all(20),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFFAF9FF),
                                    borderRadius: BorderRadius.circular(18),
                                    border: Border.all(color: const Color(0xFFEDE9FE)),
                                  ),
                                  child: Row(
                                    children: [
                                      const SizedBox(
                                        width: 24,
                                        height: 24,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2.5,
                                          valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryPurple),
                                        ),
                                      ),
                                      const SizedBox(width: 14),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              'Finding healthier swaps with Gemini AI…',
                                              style: GoogleFonts.inter(
                                                fontSize: 13,
                                                fontWeight: FontWeight.w600,
                                                color: AppTheme.primaryPurple,
                                              ),
                                            ),
                                            const SizedBox(height: 2),
                                            Text(
                                              'Analyzing ingredients to eliminate harmful additives and boost nutrients.',
                                              style: GoogleFonts.inter(
                                                fontSize: 11,
                                                color: AppTheme.textSecondary,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(height: 16),
                              ],

                              // Results Heading
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    '${displayAlts.length} healthier options',
                                    style: GoogleFonts.inter(
                                      fontSize: 15,
                                      fontWeight: FontWeight.w700,
                                      color: AppTheme.textPrimary,
                                    ),
                                  ),
                                  Row(
                                    children: [
                                      const Icon(
                                        Icons.auto_awesome_rounded,
                                        size: 14,
                                        color: AppTheme.primaryPurple,
                                      ),
                                      const SizedBox(width: 4),
                                      Text(
                                        'AI Recommended',
                                        style: GoogleFonts.inter(
                                          fontSize: 12,
                                          fontWeight: FontWeight.w600,
                                          color: AppTheme.primaryPurple,
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                              const SizedBox(height: 14),

                              // Alternatives List
                              if (displayAlts.isEmpty && !_isLoading)
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    vertical: 32,
                                    horizontal: 20,
                                  ),
                                  decoration: BoxDecoration(
                                    color: AppTheme.primaryPurpleSoft,
                                    borderRadius: BorderRadius.circular(20),
                                  ),
                                  child: Column(
                                    children: [
                                      const Icon(
                                        Icons.check_circle_outline_rounded,
                                        color: AppTheme.greenDeep,
                                        size: 40,
                                      ),
                                      const SizedBox(height: 10),
                                      Text(
                                        originalScore >= 75
                                            ? 'Great Choice Already!'
                                            : 'No Filtered Swaps',
                                        style: GoogleFonts.inter(
                                          fontSize: 16,
                                          fontWeight: FontWeight.w700,
                                          color: AppTheme.textPrimary,
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        originalScore >= 75
                                            ? 'This product already has a high nutritional score ($originalScore/100).'
                                            : 'Try selecting "All" to view all available healthy alternatives.',
                                        textAlign: TextAlign.center,
                                        style: GoogleFonts.inter(
                                          fontSize: 13,
                                          color: AppTheme.textSecondary,
                                          height: 1.4,
                                        ),
                                      ),
                                    ],
                                  ),
                                )
                              else
                                ...displayAlts.map((swap) {
                                  final ptsDiff = swap.score - originalScore;
                                  return Padding(
                                    padding: const EdgeInsets.only(bottom: 14),
                                    child: _buildAlternativeCard(swap, ptsDiff),
                                  );
                                }),

                              // ── Grocery Shopping Tips from Gemini ──────────────
                              if (_aiResult != null && _aiResult!.groceryTips.isNotEmpty) ...[
                                const SizedBox(height: 10),
                                Container(
                                  padding: const EdgeInsets.all(16),
                                  decoration: BoxDecoration(
                                    gradient: const LinearGradient(
                                      colors: [Color(0xFFF6F3FF), Color(0xFFEDE9FE)],
                                      begin: Alignment.topLeft,
                                      end: Alignment.bottomRight,
                                    ),
                                    borderRadius: BorderRadius.circular(18),
                                    border: Border.all(color: const Color(0xFFDDD6FE)),
                                  ),
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Container(
                                            width: 26,
                                            height: 26,
                                            alignment: Alignment.center,
                                            decoration: BoxDecoration(
                                              color: AppTheme.primaryPurple,
                                              borderRadius: BorderRadius.circular(13),
                                            ),
                                            child: const Icon(
                                              Icons.shopping_bag_outlined,
                                              size: 14,
                                              color: Colors.white,
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Text(
                                            'Smart Grocery Shopping Tips',
                                            style: GoogleFonts.inter(
                                              fontSize: 14,
                                              fontWeight: FontWeight.w700,
                                              color: AppTheme.primaryPurpleDark,
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 10),
                                      ..._aiResult!.groceryTips.map(
                                        (tip) => Padding(
                                          padding: const EdgeInsets.only(bottom: 6),
                                          child: Row(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              const Text('💡 ', style: TextStyle(fontSize: 12)),
                                              Expanded(
                                                child: Text(
                                                  tip,
                                                  style: GoogleFonts.inter(
                                                    fontSize: 12,
                                                    color: AppTheme.textPrimary,
                                                    height: 1.4,
                                                  ),
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],

                              const SizedBox(height: 14),

                              // Disclaimer copy (Figma #2:2128)
                              Text(
                                'Different foods serve different dietary needs — compare full ingredients and nutritional portions too.',
                                style: GoogleFonts.inter(
                                  fontSize: 11,
                                  color: AppTheme.textMuted,
                                  height: 1.5,
                                ),
                              ),
                              const SizedBox(height: 16),

                              // Brand Promise (Figma #12:88)
                              Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Container(
                                    width: 22,
                                    height: 22,
                                    alignment: Alignment.center,
                                    decoration: BoxDecoration(
                                      color: AppTheme.primaryPurple,
                                      borderRadius: BorderRadius.circular(11),
                                    ),
                                    child: const Icon(
                                      Icons.eco_rounded,
                                      color: Colors.white,
                                      size: 13,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    'willow · more clarity, less guesswork.',
                                    style: GoogleFonts.inter(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color: AppTheme.primaryPurple,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 24),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String value, String label) {
    final isSelected = _selectedFilter == value;
    return GestureDetector(
      onTap: () => setState(() => _selectedFilter = value),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primaryPurple : const Color(0xFFF3F4F6),
          borderRadius: BorderRadius.circular(100),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: AppTheme.primaryPurple.withValues(alpha: 0.25),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ]
              : null,
        ),
        child: Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
            color: isSelected ? Colors.white : AppTheme.textSecondary,
          ),
        ),
      ),
    );
  }

  Widget _buildAlternativeCard(AlternativeSwap swap, int ptsDiff) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: AppTheme.borderLight),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryPurple.withValues(alpha: 0.08),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Card Header with Score Pill and Improvement Badge
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      gradient: AppTheme.scoreGradient(swap.score),
                      borderRadius: BorderRadius.circular(100),
                    ),
                    child: Text(
                      '${swap.score}/100',
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  if (ptsDiff > 0) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: AppTheme.greenSoftBg,
                        borderRadius: BorderRadius.circular(100),
                      ),
                      child: Text(
                        '+$ptsDiff pts ↑',
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.greenSuccess,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
              if (swap.swapType != null && swap.swapType!.isNotEmpty)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF3F4F6),
                    borderRadius: BorderRadius.circular(100),
                  ),
                  child: Text(
                    swap.swapType!,
                    style: GoogleFonts.inter(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),

          // Product Row
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 60,
                height: 60,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Color(0xFFEDE9FE), Color(0xFFC7F7F5)],
                  ),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.eco_rounded,
                  color: AppTheme.primaryPurple,
                  size: 30,
                ),
              ),
              const SizedBox(width: 14),

              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      swap.name,
                      style: GoogleFonts.inter(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    if (swap.brand != null && swap.brand!.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text(
                        swap.brand!,
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.primaryPurple,
                        ),
                      ),
                    ],
                    const SizedBox(height: 3),
                    Text(
                      swap.price,
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),

          // Why It's Healthier Section
          if (swap.whyHealthier != null && swap.whyHealthier!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFF0FDF4),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFDCFCE7)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.check_circle_rounded,
                    size: 15,
                    color: AppTheme.greenDeep,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      swap.whyHealthier!,
                      style: GoogleFonts.inter(
                        fontSize: 12,
                        color: const Color(0xFF166534),
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],

          // Avoided Harmful Ingredients Chips
          if (swap.avoidedIngredients.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children: [
                ...swap.avoidedIngredients.map(
                  (ing) => Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppTheme.redSoftBg,
                      borderRadius: BorderRadius.circular(100),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.block_rounded, size: 10, color: AppTheme.redDanger),
                        const SizedBox(width: 4),
                        Text(
                          'Zero $ing',
                          style: GoogleFonts.inter(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: AppTheme.redDanger,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ],

          // Key Benefits Chips
          if (swap.keyBenefits.isNotEmpty) ...[
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children: [
                ...swap.keyBenefits.map(
                  (ben) => Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: AppTheme.greenSoftBg,
                      borderRadius: BorderRadius.circular(100),
                    ),
                    child: Text(
                      '✓ $ben',
                      style: GoogleFonts.inter(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: AppTheme.greenDeep,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

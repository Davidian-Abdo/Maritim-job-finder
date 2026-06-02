import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api_client.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  List<String> _keywords = [];
  List<String> _availableSources = [];
  List<String> _selectedSources = [];
  bool _isLoading = false;

  // Scraping state
  DateTime? _lastScrape;
  int _newJobsCount = 0;
  bool _scheduleActive = false;
  String? _cronExpression;
  final TextEditingController _cronController = TextEditingController();
  final TextEditingController _keywordController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  @override
  void dispose() {
    _cronController.dispose();
    _keywordController.dispose(); // Important!
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final api = context.read<ApiClient>();
      final keywords = await api.getKeywords();
      final sources = await api.getAvailableSources();
      final profile = await api.getProfile();
      final status = await api.getScrapeStatus();
      final schedule = await api.getSchedule();

      setState(() {
        _keywords = keywords;
        _availableSources = sources['sources']?.cast<String>() ?? [];
        _selectedSources = profile['selected_sources']?.cast<String>() ?? [];
        _lastScrape = status['last_scrape'] != null
            ? DateTime.parse(status['last_scrape'])
            : null;
        _newJobsCount = status['new_jobs_count'] ?? 0;
        _scheduleActive = schedule['is_active'] ?? false;
        _cronExpression = schedule['cron_expression'];
        _cronController.text = _cronExpression ?? '';
      });
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error loading profile: $e')),
      );
    } finally {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _triggerScrape() async {
    try {
      await context.read<ApiClient>().triggerScrape();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Scrape started in background')),
      );
      Future.delayed(const Duration(seconds: 2), _loadData);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  Future<void> _saveSchedule() async {
    try {
      await context.read<ApiClient>().setSchedule(
            _scheduleActive,
            _cronController.text.isNotEmpty ? _cronController.text : null,
          );
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Schedule saved')),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  Future<void> _addKeyword(String kw) async {
    if (kw.trim().isEmpty) return;
    try {
      await context.read<ApiClient>().addKeyword(kw.trim());
      _keywordController.clear();
      _loadData(); // refresh the keyword list
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  Future<void> _deleteKeyword(String kw) async {
    try {
      await context.read<ApiClient>().deleteKeyword(kw);
      _loadData();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
  }

  Future<void> _saveSources() async {
    try {
      await context.read<ApiClient>().updateProfile(
            selectedSources: _selectedSources,
          );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error saving sources: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Keywords card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Your Keywords',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: _keywords.map((kw) => Chip(
                      label: Text(kw),
                      onDeleted: () => _deleteKeyword(kw),
                    )).toList(),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _keywordController, // Added controller
                          decoration: const InputDecoration(
                            hintText: 'Add keyword',
                            border: OutlineInputBorder(),
                          ),
                          onSubmitted: _addKeyword,
                        ),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton(
                        onPressed: () => _addKeyword(_keywordController.text),
                        child: const Text('Add'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Sources card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Job Sources',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  ..._availableSources.map((source) => CheckboxListTile(
                    title: Text(source),
                    value: _selectedSources.contains(source),
                    onChanged: (checked) async {
                      if (checked == true) {
                        _selectedSources.add(source);
                      } else {
                        _selectedSources.remove(source);
                      }
                      setState(() {});
                      await _saveSources();
                    },
                  )),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),

          // Scraping card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Scraping',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('Last scrape: ${_lastScrape != null ? _lastScrape!.toLocal() : 'Never'}'),
                      Text('New jobs: $_newJobsCount'),
                    ],
                  ),
                  const SizedBox(height: 12),
                  ElevatedButton.icon(
                    onPressed: _triggerScrape,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Scrape Now'),
                  ),
                  const Divider(),
                  // Schedule switch
                  Row(
                    children: [
                      const Text('Enable automatic scraping'),
                      Switch(
                        value: _scheduleActive,
                        onChanged: (val) {
                          setState(() => _scheduleActive = val);
                          _saveSchedule();
                        },
                      ),
                    ],
                  ),
                  if (_scheduleActive) ...[
                    const SizedBox(height: 8),
                    TextField(
                      controller: _cronController,
                      decoration: const InputDecoration(
                        labelText: 'Cron expression (e.g. 0 9 * * *)',
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (_) => _saveSchedule(),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
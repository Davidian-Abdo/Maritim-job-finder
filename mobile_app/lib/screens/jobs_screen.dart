import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:pull_to_refresh/pull_to_refresh.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api_client.dart';
import 'dart:async'; // for Timer (debounce)

class JobsScreen extends StatefulWidget {
  const JobsScreen({super.key});

  @override
  State<JobsScreen> createState() => _JobsScreenState();
}

class _JobsScreenState extends State<JobsScreen> {
  final RefreshController _refreshController = RefreshController();
  final ScrollController _scrollController = ScrollController();

  List<Job> _jobs = [];
  final Set<int> _savedJobIds = {};
  bool _isLoading = false;
  bool _hasMore = true;
  int _page = 0;
  final int _limit = 20;

  // Existing filters (rank, location, vessel) – we keep them
  String? _selectedRank;
  String? _selectedLocation;
  String? _selectedVessel;

  // NEW: Controllers for the new text filters
  final TextEditingController _titleController = TextEditingController();
  final TextEditingController _vesselController = TextEditingController();
  final TextEditingController _companyController = TextEditingController();
  final TextEditingController _locationController = TextEditingController();
  // Debouncer timer
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _fetchJobs(refresh: true);
    _fetchSavedJobs();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _locationController.dispose();
    _titleController.dispose();
    _vesselController.dispose();
    _companyController.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      if (!_isLoading && _hasMore) {
        _fetchJobs(refresh: false);
      }
    }
  }

  // Called whenever any filter changes (with debounce)
  void _onFilterChanged(String _) {
    if (_debounce?.isActive ?? false) _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 500), () {
      _fetchJobs(refresh: true);
    });
  }

  Future<void> _fetchJobs({bool refresh = true}) async {
    if (refresh) {
      _page = 0;
      _hasMore = true;
    }

    setState(() => _isLoading = true);
    try {
      final api = context.read<ApiClient>();
      final jobs = await api.getJobs(
        rank: _selectedRank,
        location: _selectedLocation?.trim().isEmpty == true
            ? null
            : _selectedLocation?.trim(),
        // NEW: pass the filter values
        vesselType: _vesselController.text.isNotEmpty
            ? _vesselController.text
            : null,
        title: _titleController.text.isNotEmpty ? _titleController.text : null,
        company: _companyController.text.isNotEmpty ? _companyController.text : null,
        limit: _limit,
        offset: _page * _limit,
      );

      if (!mounted) return;

      setState(() {
        if (refresh) {
          _jobs = jobs;
        } else {
          _jobs.addAll(jobs);
        }
        if (jobs.length < _limit) _hasMore = false;
        _page++;
      });

      if (refresh) _refreshController.refreshCompleted();
    } catch (e) {
      if (!mounted) return;
      if (refresh) _refreshController.refreshFailed();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error fetching jobs: $e')),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _fetchSavedJobs() async {
    try {
      final api = context.read<ApiClient>();
      final saved = await api.getSavedJobs();
      if (!mounted) return;
      setState(() {
        _savedJobIds
          ..clear()
          ..addAll(saved.map((j) => j.id));
      });
    } catch (_) {}
  }

  Future<void> _toggleSaveJob(Job job) async {
    final api = context.read<ApiClient>();
    final isSaved = _savedJobIds.contains(job.id);

    try {
      if (isSaved) {
        await api.unsaveJob(job.id);
        setState(() => _savedJobIds.remove(job.id));
      } else {
        await api.saveJob(job.id);
        setState(() => _savedJobIds.add(job.id));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e')),
        );
      }
    }
  }

  Future<void> _openJobUrl(String urlString) async {
    final uri = Uri.tryParse(urlString);
    if (uri == null || !uri.hasScheme) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Invalid job link')),
      );
      return;
    }
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading && _jobs.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    // Wrap everything in a Column to place filters above the list
    return Column(
      children: [
        // NEW: Filter row
        Padding(
          padding: const EdgeInsets.all(8.0),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _titleController,
                  decoration: const InputDecoration(
                    labelText: 'Title',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: _onFilterChanged,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _vesselController,
                  decoration: const InputDecoration(
                    labelText: 'Vessel type',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: _onFilterChanged,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _companyController,
                  decoration: const InputDecoration(
                    labelText: 'Company',
                    border: OutlineInputBorder(),
                  ),
                  onChanged: _onFilterChanged,
                ),
              ),
            ],
          ),
        ),
        // The job list (expanded to take remaining space)
        Expanded(
          child: SmartRefresher(
            controller: _refreshController,
            onRefresh: () => _fetchJobs(refresh: true),
            child: ListView.builder(
              controller: _scrollController,
              itemCount: _jobs.length,
              itemBuilder: (_, i) {
                final job = _jobs[i];
                final isSaved = _savedJobIds.contains(job.id);

                return Card(
                  child: ListTile(
                    // NEW: Show "NEW" badge if job.isNew is true
                    leading: job.isNew
                        ? Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.green,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'NEW',
                              style: TextStyle(
                                  color: Colors.white, fontSize: 10),
                            ),
                          )
                        : null,
                    title: Text(job.title),
                    subtitle: Text(
                        '${job.company ?? 'Unknown'} • ${job.location ?? 'Unknown'}'),
                    trailing: IconButton(
                      icon: Icon(isSaved
                          ? Icons.bookmark
                          : Icons.bookmark_border),
                      onPressed: () => _toggleSaveJob(job),
                    ),
                    onTap: () => _openJobUrl(job.url),
                  ),
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}
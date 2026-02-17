import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:pull_to_refresh/pull_to_refresh.dart';
import 'package:url_launcher/url_launcher.dart';
import '../api_client.dart';

class JobsScreen extends StatefulWidget {
  const JobsScreen({super.key});

  @override
  State<JobsScreen> createState() => _JobsScreenState();
}

class _JobsScreenState extends State<JobsScreen> {
  final RefreshController _refreshController = RefreshController();
  final ScrollController _scrollController = ScrollController();

  List<Job> _jobs = [];
  final Set<int> _savedJobIds = {};   // ✅ FIX
  bool _isLoading = false;
  bool _hasMore = true;
  int _page = 0;
  final int _limit = 20;

  String? _selectedRank;
  String? _selectedLocation;
  String? _selectedVessel;
  final TextEditingController _locationController = TextEditingController();

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
        location: _selectedLocation?.trim().isEmpty == true ? null : _selectedLocation?.trim(),
        vesselType: _selectedVessel,
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
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
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

    return SmartRefresher(
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
              title: Text(job.title),
              subtitle: Text('${job.company ?? 'Unknown'} • ${job.location ?? 'Unknown'}'),
              trailing: IconButton(
                icon: Icon(isSaved ? Icons.bookmark : Icons.bookmark_border),
                onPressed: () => _toggleSaveJob(job),
              ),
              onTap: () => _openJobUrl(job.url),
            ),
          );
        },
      ),
    );
  }
}

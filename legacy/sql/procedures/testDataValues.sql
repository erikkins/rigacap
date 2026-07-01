-- SqlProcedure: [dbo].[testDataValues]

set nocount on
BEGIN

	declare @stockID int
	declare @atwhen datetime
	declare @buy int
	set @buy=0

	select @stockID=stockID, @atwhen=atwhen
	from stockBuy where buyID=@buyID

	declare @mean money
	declare @stdev money
	declare @max money, @min money
	declare @closeCount int
	declare @countbelow int, @countabove int
	select @mean = dbo.fn200DMA (@stockID, @atwhen)
	declare @ret bit
	--now for the 50 days, see how many points are outside the first stdev

		declare @trep table
		(
			cnt int IDENTITY(1,1),
			price money,
			volume bigint,
			atwhen datetime
		)
		insert into @trep
			select top 200 price, volume, atwhen
			from stockdata
			where stockID = @stockID
			and atwhen < @atwhen
			order by atwhen desc

		select @stdev = stdev(price) from @trep
				
	declare @meanratio float

	select @meanratio = (@stdev/@mean) * 100	
	select @max = max(price), @min=min(price) from @trep
	
	/*
	if @meanratio > 10
		begin
			--the stdev is more than 10%, let's bring it in a bit to test a tighter variance
			declare @mult float
			select @mult = (100 - (@meanratio-10))/100
			select @meanratio meanratio, @mult mult, (@mean-(@stdev*@mult)) low, (@mean+(@stdev*@mult)) high
			select @closeCount = count(*) from @trep where price between (@mean-(@stdev*@mult)) and (@mean+(@stdev*@mult))
			select @countBelow = count(*) from @trep where price between (@mean-(@stdev*@mult)) and @mean
			select @countAbove = count(*) from @trep where price between @mean and (@mean+(@stdev*@mult))
		end
	else
	*/
		begin
			select @closeCount = count(*) from @trep where price between (@mean-(@stdev)) and (@mean+(@stdev))		
			select @countBelow = count(*) from @trep where price < (@mean-@stdev) and cnt < 100
			select @countAbove = count(*) from @trep where price > (@mean+@stdev) and cnt < 100
		end
	
	if @closeCount > 80
		begin
			select @ret=1
		end
	else
		begin
			select @ret=0
		end
	

	declare @toohigh int, @toolow int
	select @toohigh = count(*) from @trep
	where price > @mean + (2*@stdev)
	select @toolow = count(*) from @trep
	where price < @mean - (2*@stdev)

	--let's do a moving slope (20 samples, 10 days each)
	declare @samples int, @sampslope float, @sampstart datetime, @sampend datetime, @sampcntstart int, @sampcntend int
	select @samples = 1
	select @sampcntstart = 200, @sampcntend=191
	declare @avgprice money, @50DMA money, @fiftySpot bit, @50spotcnt int, @dwap money, @dwapSpot bit, @dwapspotcnt int
	declare @avgvolume bigint

	declare @slopetb table
	(
		cnt int IDENTITY(1,1),
		slope float,
		startdate datetime,
		fiftySpot bit,
		dwapSpot bit,
		averagevol float,
		[slope%] decimal(3,1),
		[vol%] decimal(3,1),
		volumeweightedslope float,
		[vws%] decimal(3,1)
	)

	while @samples <= 20
		begin				
			select @sampstart = atwhen from @trep where cnt=@sampcntstart
			select @sampend = atwhen from @trep where cnt=@sampcntend
			
			select @avgprice = avg(price), @avgvolume = avg(volume)
			from @trep
			where atwhen between @sampstart and @sampend

			declare @midDate datetime
			select @middate = atwhen from @trep where cnt = @sampcntstart-5

			select @50DMA = dbo.fn50DMA(@stockID, @midDate)
			select @dwap = dbo.fnDWAP(@stockID, @midDate)

			if @avgprice > @50DMA
				begin
				select @fiftySpot = 1
				end
			else
				begin
				select @fiftySpot = 0
				end

			if @avgprice > @dwap
				begin
					select @dwapspot = 1
				end
			else
				begin
					select @dwapspot = 0
				end


			select @sampslope = dbo.fnSlope(@stockID, @sampstart, @sampend)
			insert into @slopetb
				select @sampslope, @sampstart, @fiftySpot, @dwapspot, @avgVolume, null, null, @sampslope*@avgVolume, null
			select @samples = @samples+1
			select @sampcntstart = @sampcntstart - 10
			select @sampcntend = @sampcntend - 10			
		end

	--now update the percentages
	declare @totalslope float, @totalvol float, @minslope float, @totalvws float, @minvws float
	select @minslope = abs(min(slope)) from @slopetb --this is to offset so we have no negatory values	
	select @minvws = abs(min(volumeweightedslope)) from @slopetb
	select @totalslope = sum(slope+@minslope) from @slopetb
	select @totalvol = sum(averagevol) from @slopetb	
	select @totalvws = sum(volumeweightedslope + @minvws) from @slopetb
	
	update @slopetb
	set [slope%] = ((slope+@minslope)/@totalslope)*100,
	[vol%] = (averagevol/@totalvol)*100,
	[vws%] = ((volumeweightedslope+@minvws)/@totalvws)*100
		
	
	--select * from @slopetb

	declare @positiveSlope int
	select @positiveSlope= count(*) from @slopetb
	where slope > 0
	and cnt > 15

	declare @avgFinalSlope float
	select @avgFinalSlope = avg(slope) from @slopetb
	
	declare @lastSlope float
	select @lastSlope = slope from @slopetb where cnt=20
	if @lastSlope < 0
		begin
			select @lastSlope = slope
			from @slopetb
			where cnt < 20
			and slope > 0			
		end
	

	declare @last50spot int
	select @last50spot = fiftyspot from @slopetb where slope=@lastSlope and cnt > 10

	declare @nextToLast float
	select @nextToLast = slope 
	from @slopetb where cnt = (select cnt from @slopetb where slope=@lastSlope and cnt > 10)-1

	--select @50spotcnt = count(*) from @slopetb s1
	--where (slope > 0 and cnt=20) 
	if @test = 1
	select * from @slopetb

	declare @19vol float, @20vol float, @19slope float, @20slope float, @19dwap int, @20dwap int, @maxslope float
	select @19vol = [vol%], @19slope=slope, @19dwap=dwapspot from @slopetb where cnt=19
	select @20vol = [vol%], @20slope=slope, @20dwap=dwapspot from @slopetb where cnt=20
	select @maxslope = max(slope) from @slopetb
	if @19slope < 0 and @19vol > @20vol and @20slope > 0
		begin
			select @buy=1
		end

	if @19slope < 0 and @19vol < @20vol and @20slope > 0 and @19dwap=1
		begin
			select @buy=3
		end
		
	if @20slope=@maxslope and @20vol>@19vol
		begin
			select @buy=5
		end

	if @20slope < 0 and @20vol > @19vol and @19slope > 0 and @20dwap=1 and @19dwap=0
		begin
			select @buy=2
		end


	if exists (select * from @slopetb where (cnt=20 and slope>0)) and exists (select * from @slopetb where (cnt=19 and slope < 0))
		begin
			select @50spotcnt = 1
		end
	else
		begin
			select @50spotcnt = 0
		end


	if @lastSlope >= @avgFinalSlope * 4
		begin
			if exists (select * from @slopetb where dwapspot > 0 and cnt > 10 and @last50spot=0)
				begin
					select @dwapspotcnt = 1
				end
			else
				begin
					if @lastSlope >= @avgFinalSlope * 20
						begin	
							
							select @dwapspotcnt = 1
						end
					else
						begin
							--if dwapspot is 1 and 50spot is 1 on the next to last slope, then good							
							if @nextTolast < 0 and exists (select * from @slopetb where slope=@nextToLast and dwapspot=1 and fiftyspot=1)
								begin
								select @dwapspotcnt = 1
								end
							else
								begin
								select @dwapspotcnt = 0
								end
						end
				end

		end
	else
		begin
			--now the case where next to last is negative and last is positive
			if @lastSlope > @avgFinalSlope
				begin
					if @nextToLast < 0 and @lastSlope > 0
						begin
							select @dwapspotcnt = 1
						end
					else
						begin
							select @dwapspotcnt = 0
						end
				end
			else
				begin
					select @dwapspotcnt = 0
				end
		end
	
	if @test=1
		select @last50spot last50spot, @lastslope lastSlope, @nextToLast nextTolast	

	
	if @test=0
		begin
			declare @slope float, @yint money
			select @slope = dbo.fnSlope(@stockID, dateadd(day,-14,@atwhen), @atwhen)
			select @yint = dbo.fnSlopeIntercept(@stockID,dateadd(day,-14,@atwhen), @atwhen)
			select @buyid BuyID,@stockID stockID, @ret returnValue, @mean mean, @stdev [stdev], (@stdev/@mean)*100 [stdev%], @closeCount closeCount, @countBelow below, @countAbove above, @max maxPrice, @min minPrice, @toohigh TooHigh, @toolow TooLow, @slope Slope,@yint [50DYInt],@positiveSlope positiveslope, @avgfinalslope avgfinalslope,@50spotcnt FiftySpotCount, @dwapspotcnt DWAPSpotCount, @watchName watchName, @buy Buy
		end

	if @test=2
		begin
			select @buy Buy
		end

END
set nocount off
